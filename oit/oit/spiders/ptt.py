import logging
import sys, traceback

from datetime import datetime
from time import gmtime, strftime

import html2text
import scrapy

from scrapy.http import FormRequest

from oit.items import PostItem


class PTTSpider(scrapy.Spider):
    name = 'ptt'
    allowed_domains = ['ptt.cc']
    start_urls = ('https://www.ptt.cc/bbs/Gossiping/index.html', )

    _retries = 0
    MAX_RETRY = 1

    _pages = 0
    MAX_PAGES = 3

    def parse(self, response):
        if len(response.xpath('//div[@class="over18-notice"]')) > 0:
            if self._retries < PTTSpider.MAX_RETRY:
                self._retries += 1
                # logging.warning('retry {} times...'.format(self._retries))
                yield FormRequest.from_response(response,
                                                formdata={'yes': 'yes'},
                                                callback=self.parse)
            else:
                logging.warning('you cannot pass')

        else:
            self._pages += 1
            for href in response.css('.r-ent > div.title > a::attr(href)'):
                url = response.urljoin(href.extract())
                yield scrapy.Request(url, callback=self.parse_post)

            if self._pages < PTTSpider.MAX_PAGES:
                print(self._pages)
                next_page = response.xpath(
                    '//div[@id="action-bar-container"]//a[contains(text(), "上頁")]/@href')
                if next_page:
                    url = response.urljoin(next_page[0].extract())
                    logging.warning('follow {}'.format(url))
                    yield scrapy.Request(url, self.parse)
                else:
                    logging.warning('no next page')
            else:
                logging.warning('max pages reached')

    def parse_post(self, response):
        item = PostItem()

        item['title'] = response.xpath('//meta[@property="og:title"]/@content').extract_first(default='not-found')
				 
        item['author'] = response.xpath(
            '//div[@class="article-metaline"]/span[text()="作者"]/following-sibling::span[1]/text()').extract_first(default='not-found').split(' ')[0]

        datetime_str = response.xpath('//div[@class="article-metaline"]/span[text()="時間"]/following-sibling::span[1]/text()').extract_first(default=strftime('%a %b %d %H:%M:%S %Y', gmtime()))
        item['date'] = datetime.strptime(datetime_str, '%a %b %d %H:%M:%S %Y')

        converter = html2text.HTML2Text()
        converter.ignore_links = True

        item['content'] = converter.handle(response.xpath('//div[@id="main-content"]').extract_first(default='not-found'))
        comments = []
        total_score = 0
        for comment in response.xpath('//div[@class="push"]'):
            push_tag = comment.css('span.push-tag::text').extract_first(default='')
            push_user = comment.css('span.push-userid::text').extract_first(default='')
            push_content = comment.css('span.push-content::text').extract_first(default='')

            if '推' in push_tag:
                score = 1
            elif '噓' in push_tag:
                score = -1
            else:
                score = 0

            total_score += score

            comments.append({'user': push_user,
                             'content': push_content,
                             'score': score})

        item['comments'] = comments
        item['score'] = total_score
        item['url'] = response.url
        #print(item['title'],item['author'],item['date'],item['content'],item['comments'],item['score'],item['url'])

        yield item