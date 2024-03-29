import argparse
import datetime
import html
import json
import re
from io import BytesIO
from typing import Tuple

import qrcode
import requests
from PIL import Image, ImageDraw, ImageFont


def main() -> None:
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


def unescape_html(text: str) -> str:
    html_tag_regex = re.compile('<.*?>')
    text = re.sub(html_tag_regex, '', text)
    return html.unescape(text)


def generate_random_summary(user_agent_email: str, title_font_path: str, body_font_path: str,
                            language_code: str = 'en') -> Image:
    title, description, extract, thumbnail_url = load_random(user_agent_email, language_code)
    thumbnail = load_image(thumbnail_url)
    summary = create_summary_image(title, description, extract, thumbnail, title_font_path, body_font_path)

    return summary


def generate_daily_summary(user_agent_email: str, title_font_path: str, body_font_path: str, language_code: str = 'en',
                           date: str = None) -> Image:
    title, description, extract, thumbnail_url, article_url = load_tfa(user_agent_email, language_code, date)
    thumbnail = load_image(thumbnail_url) if thumbnail_url else None
    summary = create_summary_image(title, description, extract, thumbnail, title_font_path, body_font_path, article_url)

    return summary


def load_tfa(user_agent_email: str, language_code: str, date: str) -> Tuple[str, str, str, str, str]:
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
    # Check if description is available
    if 'description' in response['tfa']:
        description = response['tfa']['description']
    else:
        description = 'From Wikipedia, the free encyclopedia'
    extract = response['tfa']['extract']
    thumbnail_url = response['tfa']['thumbnail']['source'] if 'thumbnail' in response['tfa'] else None
    article_url = response['tfa']['content_urls']['desktop']['page']

    title = unescape_html(title)

    return title, description, extract, thumbnail_url, article_url


def load_random(user_agent_email: str, language_code: str) -> Tuple[str, str, str, str]:
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

    title = unescape_html(title)

    return title, description, extract, thumbnail_url


def load_image(url: str) -> Image:
    headers = {
        # 'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
        'User-Agent': 'WikiSummary (florian.spiess@unibas.ch)'
    }
    response = requests.get(url, headers=headers)
    b = BytesIO(response.content)
    return Image.open(b)


def rescale_image(image: Image, max_dim: int) -> Image:
    """
    Rescales the given image to fit into a square with the given max dimension.
    """
    w, h = image.size
    factor = max_dim / max(w, h)
    return image.resize((int(w * factor), int(h * factor)))


def create_summary_image(title: str, description: str, extract: str, thumbnail: Image, title_font_path: str,
                         body_font_path: str, article_url: str = None) -> Image:
    """
    Creates a summary image for the given data of a Wikipedia article.

    :param title: Title of the article
    :param description: Short description of the article
    :param extract: Extract of the article
    :param thumbnail: Thumbnail image of the article
    :param title_font_path: Path to the title font file
    :param body_font_path: Path to the body font file
    :param article_url: URL to the article (if provided inserts QR code to article)
    :return: Summary image of the article
    """
    width = 600
    height = 448
    padding = 10
    extract_font_size = 18

    image = Image.new(mode='RGB', size=(width, height), color=(255, 255, 255))

    # Draw QR code if enabled
    qr_size = 0
    if article_url:
        qr_builder = qrcode.QRCode(
            border=3,
            box_size=3
        )
        qr_builder.add_data(article_url)
        qr = qr_builder.make_image()
        qr_size = qr.pixel_size
        image.paste(qr, (width - qr_size, height - qr_size))

    # Draw thumbnail after QR code to allow resizing if qr code is particularly large
    if thumbnail:
        # Rescale and draw thumbnail
        max_dim = 300
        thumbnail = rescale_image(thumbnail, max_dim)
        tw, th = thumbnail.size

        # If thumbnail height would overlap with QR code, resize thumbnail further
        if height - qr_size - padding < th:
            thumbnail = rescale_image(thumbnail, height - qr_size - padding)
            tw, th = thumbnail.size

        thumbnail_start = width - tw - padding

        # Check if thumbnail has an alpha channel (transparency)
        if thumbnail.mode in ['RGBA', 'LA']:
            mask = thumbnail  # use thumbnail as mask
        else:
            mask = Image.new('L', thumbnail.size, 255)  # create a new white 'L' image as mask

        image.paste(thumbnail, (thumbnail_start, padding), mask=mask)
    else:
        tw, th = 0, 0
        thumbnail_start = width

    # Draw title
    draw = ImageDraw.Draw(image)

    title_space = thumbnail_start - (2 * padding)
    title_size = (0, 0)
    for size in range(32, 8, -1):
        title_font = ImageFont.truetype(title_font_path, size)
        title_size = title_font.getbbox(title)[2:]
        if title_size[0] > title_space:
            continue
        draw.text((padding, padding), title, fill=(0, 0, 0), font=title_font)
        break

    line_height = padding + title_size[1] + 3
    draw.line((padding, line_height, thumbnail_start - padding, line_height), fill=(0, 0, 0))

    # Draw description
    description_size = (0, 0)
    for size in range(24, 8, -1):
        description_font = ImageFont.truetype(body_font_path, size)
        description_size = description_font.getbbox(description)[2:]
        if description_size[0] > title_space:
            continue
        draw.text((padding, line_height + padding), description, fill=(0, 0, 0), font=description_font)
        break

    # Draw extract
    extract_start = line_height + int(padding * 2.2) + description_size[1]
    extract_font = ImageFont.truetype(body_font_path, extract_font_size)

    # Remove leading and trailing white spaces from extract before splitting
    parts = extract.strip().split(' ')

    current_line = parts[0]
    current_height = extract_start
    space = title_space
    for part in parts[1:]:
        line = current_line + ' ' + part
        line_size = extract_font.getbbox(line)[2:]
        if line_size[0] > space:
            # If text doesn't fit
            if current_height + (2 * line_size[1]) + padding > height:
                final_line = ' '.join(current_line.split()[:-1] + ['...']) if \
                    extract_font.getbbox(current_line + ' ...')[2] > space else current_line + ' ...'
                draw.text((padding, current_height), final_line, fill=(0, 0, 0), font=extract_font)
                current_height = height
                break
            # Regular
            draw.text((padding, current_height), current_line, fill=(0, 0, 0), font=extract_font)
            current_line = part
            current_height += line_size[1] + padding
            if current_height > (2 * padding) + th:
                space = width - (2 * padding)
            if current_height + line_size[1] > height - qr_size:
                space = min(width - padding - qr_size, space)
        else:
            current_line = line

    if current_height < height:
        draw.text((padding, current_height), current_line, fill=(0, 0, 0), font=extract_font)

    return image


if __name__ == '__main__':
    main()
