import argparse
import datetime
import json
import re
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('article', help='Type of article to load. Either "tfa" today\'s featured article, or "random".',
                        choices=['tfa', 'random'])
    parser.add_argument('user_agent_email', help='Email address to use in user agent string.')
    parser.add_argument('--language', help='The language code for the version of Wikipedia to get articles from.',
                        default='en')
    parser.add_argument('--title-font', help='Path to the font used to render the article title. Wikipedia uses '
                                             'Georgia.', default='fonts/Georgia.ttf')
    parser.add_argument('--body-font', help='Path to the font used to render the article body. Wikipedia uses '
                                            'Helvetica.', default='fonts/Helvetica.ttc')
    parser.add_argument('--date', help='In case of today\'s featured article the date to get the featured article from '
                                       'in format %Y/%m/%d. Defaults to the current date.')

    args = parser.parse_args()
    article = args.article
    user_agent_email = args.user_agent_email
    language_code = args.language

    title_font_path = args.title_font
    body_font_path = args.body_font

    summary = None

    if article == 'tfa':
        summary = generate_daily_summary(user_agent_email, title_font_path, body_font_path, language_code, args.date)
    elif article == 'random':
        summary = generate_random_summary(user_agent_email, title_font_path, body_font_path, language_code)

    if summary is not None:
        summary.show()


def generate_random_summary(user_agent_email, title_font_path, body_font_path, language_code='en'):
    title, description, extract, thumbnail_url = load_random(user_agent_email, language_code)
    thumbnail = load_image(thumbnail_url)
    summary = create_summary_image(title, description, extract, thumbnail, title_font_path, body_font_path)

    return summary


def generate_daily_summary(user_agent_email, title_font_path, body_font_path, language_code='en', date=None):
    title, description, extract, thumbnail_url = load_tfa(user_agent_email, language_code, date)
    thumbnail = load_image(thumbnail_url)
    summary = create_summary_image(title, description, extract, thumbnail, title_font_path, body_font_path)

    return summary


def load_tfa(user_agent_email, language_code, date):
    today = datetime.datetime.now()
    if date is None:
        date = today.strftime('%Y/%m/%d')

    headers = {
        # 'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
        'User-Agent': f'WikiPreview ({user_agent_email})'
    }

    # Build request URL
    base_url = 'https://api.wikimedia.org/feed/v1/wikipedia/'
    url = base_url + language_code + '/featured/' + date
    response = requests.get(url, headers=headers)
    response = json.loads(response.text)

    title = response['tfa']['titles']['display']
    description = response['tfa']['description']
    extract = response['tfa']['extract']
    thumbnail_url = response['tfa']['thumbnail']['source']

    html_tag_regex = re.compile('<.*?>')
    title = re.sub(html_tag_regex, '', title)

    return title, description, extract, thumbnail_url


def load_random(user_agent_email, language_code):
    # Using legacy Wikipedia API because I was unable to find Wikimedia random article endpoint
    url = f'https://{language_code}.wikipedia.org/api/rest_v1/page/random/summary'
    headers = {
        # 'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
        'User-Agent': f'WikiSummary ({user_agent_email})'
    }
    response = requests.get(url, headers=headers)
    response = json.loads(response.text)

    title = response['titles']['display']
    description = response['description']
    extract = response['extract']
    thumbnail_url = response['thumbnail']['source']

    html_tag_regex = re.compile('<.*?>')
    title = re.sub(html_tag_regex, '', title)

    return title, description, extract, thumbnail_url


def load_image(url):
    headers = {
        # 'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
        'User-Agent': 'WikiSummary (florian.spiess@unibas.ch)'
    }
    response = requests.get(url, headers=headers)
    b = BytesIO(response.content)
    return Image.open(b)


def create_summary_image(title, description, extract, thumbnail, title_font_path, body_font_path):
    width = 600
    height = 448
    padding = 10
    extract_font_size = 18

    image = Image.new(mode='RGB', size=(width, height), color=(255, 255, 255))

    # Rescale and draw thumbnail
    max_dim = 300
    tw, th = thumbnail.size
    factor = max_dim / max(tw, th)
    thumbnail = thumbnail.resize((int(tw * factor), int(th * factor)))
    tw, th = thumbnail.size

    thumbnail_start = width - tw - padding
    image.paste(thumbnail, (thumbnail_start, padding))

    # Draw title
    draw = ImageDraw.Draw(image)

    title_space = thumbnail_start - (2 * padding)
    title_size = (0, 0)
    for size in range(32, 8, -1):
        title_font = ImageFont.truetype(title_font_path, size)
        title_size = title_font.getsize(title)
        if title_size[0] > title_space:
            continue
        draw.text((padding, padding), title, fill=(0, 0, 0), font=title_font)
        break

    line_height = padding + title_size[1] + 2
    draw.line((padding, line_height, thumbnail_start - padding, line_height), fill=(0, 0, 0))

    # Draw description
    description_size = (0, 0)
    for size in range(24, 8, -1):
        description_font = ImageFont.truetype(body_font_path, size)
        description_size = description_font.getsize(description)
        if description_size[0] > title_space:
            continue
        draw.text((padding, line_height + padding), description, fill=(0, 0, 0), font=description_font)
        break

    # Draw extract
    extract_start = line_height + (padding * 3) + description_size[1]
    extract_font = ImageFont.truetype(body_font_path, extract_font_size)

    parts = extract.split(' ')

    current_line = parts[0]
    current_height = extract_start
    space = title_space
    for part in parts[1:]:
        line = current_line + ' ' + part
        line_size = extract_font.getsize(line)
        if line_size[0] > space:
            # If text doesn't fit
            if current_height + (2 * line_size[1]) + padding > height:
                final_line = ' '.join(current_line.split()[:-1] + ['...']) if \
                    extract_font.getsize(current_line + ' ...')[0] > space else current_line + ' ...'
                draw.text((padding, current_height), final_line, fill=(0, 0, 0), font=extract_font)
                current_height = height
                break
            # Regular
            draw.text((padding, current_height), current_line, fill=(0, 0, 0), font=extract_font)
            current_line = part
            current_height += line_size[1] + padding
            if current_height > (2 * padding) + th:
                space = width - (2 * padding)
        else:
            current_line = line

    if current_height < height:
        draw.text((padding, current_height), current_line, fill=(0, 0, 0), font=extract_font)

    return image


if __name__ == '__main__':
    main()
