#!/usr/bin/env python3
"""
Main script updating Inky Impression display on a daily basis with today's featured article from Wikipedia.
Requires the Inky Impression display connected to a compatible Raspberry Pi and the 'inky' Python package.
Updates every morning at 03:00.
"""

import argparse
import datetime
import logging
import time

from PIL import Image
from inky.inky_uc8159 import Inky

from wikipreview import generate_daily_summary


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('user_agent_email', help='Email address to use in user agent string.')
    parser.add_argument('--language', help='The language code for the version of Wikipedia to get articles from.',
                        default='en')
    parser.add_argument('--title-font', help='Path to the font used to render the article title. Wikipedia uses '
                                             'Georgia.', default='fonts/Georgia.ttf')
    parser.add_argument('--body-font', help='Path to the font used to render the article body. Wikipedia uses '
                                            'Helvetica.', default='fonts/Helvetica.ttc')
    parser.add_argument('-l', '--log-level', help='Log level for logging messages.', type=str, default='INFO',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'])

    args = parser.parse_args()
    user_agent_email = args.user_agent_email
    language_code = args.language

    title_font_path = args.title_font
    body_font_path = args.body_font

    loglevel = getattr(logging, args.log_level)
    logging.basicConfig(level=loglevel, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f'Set log level to: {logging.getLevelName(loglevel)}')

    inky = Inky()
    saturation = 0.5

    while True:
        logging.info('Cleaning...')
        clean(inky)
        try:
            logging.info('Retrieving today\'s featured article...')
            image = generate_daily_summary(user_agent_email, title_font_path, body_font_path, language_code)

            logging.info('Drawing image...')
            inky.set_image(image, saturation=saturation)
            inky.show()
        except AttributeError as e:
            logging.error(f'Encountered attribute error: {e}')

        tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)
        tomorrow.replace(hour=3, minute=0, second=0, microsecond=0)
        now = datetime.datetime.now()

        delta = tomorrow - now

        logging.info('Sleeping until tomorrow. Have a great day!')
        if delta > datetime.timedelta(0):
            time.sleep(delta.total_seconds())


def clean(inky_display):
    colours = (inky_display.RED, inky_display.BLACK, inky_display.WHITE)
    colour_names = (inky_display.colour, "black", "white")

    img = Image.new("P", (inky_display.WIDTH, inky_display.HEIGHT))

    for j, c in enumerate(colours):
        logging.info(f'Cleaning with {colour_names[j]}')
        inky_display.set_border(c)
        for x in range(inky_display.WIDTH):
            for y in range(inky_display.HEIGHT):
                img.putpixel((x, y), c)
        inky_display.set_image(img)
        inky_display.show()
        time.sleep(1)

    logging.info('Cleaning complete!')


if __name__ == '__main__':
    main()
