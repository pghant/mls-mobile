import sys
from urllib.parse import urlsplit, parse_qs
import re

import requests
from bs4 import BeautifulSoup

def _clean_string(string):
  parts = string.replace('\xa0', ' ').strip().split('\r\n')
  return ' '.join([p.strip().encode('ascii', errors='ignore').decode('utf-8') for p in parts])

def _parse_tds(tds):
  info = []
  for td in tds:
    content_i = 0
    len_content = len(td.contents)
    if len_content > 1:
      while content_i < len_content-1 and td.contents[content_i] != '\n':
        name = _clean_string(td.contents[content_i]).replace(':', '')
        value = _clean_string(td.contents[content_i+1].text)
        info.append({ 'name': name, 'value': value })
        content_i += 2
  return info

class MLS:
  def __init__(self, url):
    self.mls_num, self.soup = self._get_mls_page(url)

  def info(self):
    allinfo = {}
    title_info = self.get_title_info()
    basic_info = self.get_basic_info()
    remarks = self.get_remarks()
    property_info = self.get_property_info()
    features = self.get_features()
    other_info = self.get_other_info()
    tax_info = self.tax_info()
    rooms = self.get_rooms()
    picture_urls = self.get_picture_urls()
    important_info = self.get_important_info(basic_info, property_info, other_info)
    allinfo.update(title_info)
    allinfo.update(basic_info)
    allinfo.update(remarks)
    allinfo.update(property_info)
    allinfo.update(features)
    allinfo.update(other_info)
    allinfo.update(tax_info)
    allinfo.update(rooms)
    allinfo.update(picture_urls)
    allinfo.update(important_info)
    return allinfo

  def _get_mls_page(self, login_url):
    parsed_url = urlsplit(login_url)
    qs = parse_qs(parsed_url.query)
    mls_num = qs['mls'][0]
    report_url = f"http://vow.mlspin.com/clients/report.aspx?mls={mls_num}"
    sess = requests.session()
    sess.get(login_url)
    res = sess.get(report_url)
    return mls_num, BeautifulSoup(res.content, 'lxml')

  def get_important_info(self, basic_info, property_info, other_info):
    # bedrooms (basic), bathrooms, fee (complex), living area (property), year built (other)
    rows = [row for row in basic_info['basicInfo'] if re.match(r'Bedrooms|Bathrooms', row['name'])]
    rows.extend([row for row in property_info['propertyInfo'] if re.match(r'Approx. Living Area', row['name'])])
    rows.extend([row for row in property_info['complexInfo'] if re.match(r'Association|Fee', row['name'])])
    rows.extend([row for row in other_info['other'] if re.match(r'Year Built/Converted', row['name'])])
    return { 'importantInfo': rows }

  def get_title_info(self):
    title_table_contents = self.soup.find(string=re.compile('MLS')).find_parent('b').contents
    info = {}
    info['mlsNumber'] = _clean_string(title_table_contents[0])
    info['propertyType'] = _clean_string(title_table_contents[2])
    return info

  def get_basic_info(self):
    basic_info_table = self.soup.find(string=re.compile('MLS')).find_parents('table')[1].next_sibling.next_sibling
    info = {}
    tds = basic_info_table.find_all('td')
    info['address'] = [_clean_string(tds[0].text)]
    info['address'].append(_clean_string(tds[2].text))
    info['address'].append(_clean_string(tds[4].text))
    info['listPrice'] = _clean_string(tds[1].find('b').text)
    info['basicInfo'] = _parse_tds(tds[5:])
    directions_table = basic_info_table.next_sibling.next_sibling
    info['directions'] = _clean_string(directions_table.find('b').text)
    return info
    
  def get_remarks(self):
    remarks_table = self.soup.find(string=re.compile('Remarks')).find_parent('table').next_sibling.next_sibling
    return { 'remarks': _clean_string(remarks_table.text) }

  def get_property_info(self):
    propertyinfo_table = self.soup.find(string=re.compile('Property Information')).find_parent('table').next_sibling.next_sibling
    info = {}
    tds = propertyinfo_table.find_all('td')
    info['propertyInfo'] = _parse_tds(tds[:11])
    info['complexInfo'] = _parse_tds([*tds[14:18], tds[21]])
    info['complexInfo'].append({ 'name': _clean_string(tds[19].text), 'value': _clean_string(tds[20].text) })
    return info

  def get_features(self):
    features_table = self.soup.find(string=re.compile('Appliances')).find_parent('table')
    info = {}
    tds = features_table.find_all('td')
    info['features'] = _parse_tds(tds)
    return info

  def get_other_info(self):
    other_table = self.soup.find(string=re.compile('Other Property Info')).find_parent('table').next_sibling.next_sibling
    info = {}
    tds = other_table.find_all('td')
    info['other'] = _parse_tds(tds)
    return info

  def tax_info(self):
    other_table = self.soup.find(string=re.compile('Tax Information')).find_parent('table').next_sibling.next_sibling
    info = {}
    tds = other_table.find_all('td')
    info['taxInfo'] = _parse_tds(tds)
    return info

  def get_rooms(self):
    room_table = self.soup.find(string=re.compile('Room Levels')).find_parent('table').next_sibling.next_sibling
    trs = room_table.find_all('tr')
    def parse_room_row(tr):
      tds = tr.find_all('td')
      return {
        'room': _clean_string(tds[0].text).replace(':', ''),
        'level': _clean_string(tds[1].text),
        'size': _clean_string(tds[2].text),
        'features': _clean_string(tds[3].text)
      }
    return { 'rooms': [parse_room_row(tr) for tr in trs[1:]] }

  def get_picture_urls(self):
    gallery_url = f'http://vow.mlspin.com/clients/ListingPhotoGallery.aspx?List_No={self.mls_num}'
    res = requests.get(gallery_url)
    soup = BeautifulSoup(res.content, 'lxml')
    all_tables = soup.find_all('table')
    image_url = f'http://media.mlspin.com/photo.aspx?nopadding=1&mls={self.mls_num}'
    if len(all_tables) == 1:
      return { 'pictures': [image_url] }
    img_table = all_tables[1]
    num_imgs = len(img_table.find_all('img'))
    return { 'pictures': [f'{image_url}&n={num}' for num in range(0, num_imgs)] }