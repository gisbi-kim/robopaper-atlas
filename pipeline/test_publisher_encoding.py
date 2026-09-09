import unittest
from unittest.mock import patch
import requests
from refresh_publisher_sources import html_page

class PublisherEncodingTests(unittest.TestCase):
    def test_html_charset_overrides_requests_latin1_default(self):
        title='π*₀.₆: a VLA That Learns From Experience'
        response=requests.Response()
        response.status_code=200
        response.encoding='ISO-8859-1'
        response._content=(f'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
                           f'<meta name="citation_title" content="{title}">'
                           '<meta name="citation_author" content="José Müller">'
                           '<p>Vision–language–action doesn’t require ASCII.</p>').encode('utf-8')
        self.assertNotIn(title,response.text)  # reproduces the original bug
        with patch('refresh_publisher_sources.get',return_value=response):
            page=html_page('https://www.roboticsproceedings.org/rss22/p087.html')
        self.assertEqual(page.find('meta',attrs={'name':'citation_title'})['content'],title)
        self.assertEqual(page.find('meta',attrs={'name':'citation_author'})['content'],'José Müller')
        self.assertEqual(page.p.get_text(),'Vision–language–action doesn’t require ASCII.')

if __name__=='__main__': unittest.main()
