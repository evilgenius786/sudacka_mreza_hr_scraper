# -*- coding: cp1250 -*-
import csv
import json
import os
import threading
import traceback
from datetime import datetime
from datetime import datetime, time
from time import sleep

import requests
from bs4 import BeautifulSoup
from lxml import html
from openpyxl import Workbook
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from xlsxwriter.workbook import Workbook

threadcount = 3
t = 1
timeout = 10

debug = False
convert = False
headless = False
images = False
max = False
incognito = True
testing = False

site = "http://www.sudacka-mreza.hr/"
encoding = 'utf8'
outfile = 'out-sudacka-mreza.csv'
logfile = "log-sudacka-mreza.csv"
logxl = 'log-sudacka-mreza.xlsx'
errorfile = 'error-sudacka-mreza.txt'

semaphore = threading.Semaphore(threadcount)
lock = threading.Lock()

licitacija = 'https://licitacija.hr/sudacka-mreza.hr.php'
headers = ['Naziv', 'Sud', 'Stečajni dužnik', 'Kategorija imovine', 'Rok za ponudu', 'Novi datum za ponude',
           'Vrijednost', 'Napomena', 'Status', 'Broj postupka', 'Stečajni upravitelj', 'Vrsta imovine', 'Datum dražbe',
           'Novi datum dražbe', 'Oglas', 'Link', 'Datoteka 1', 'Datoteka 2', 'Datoteka 3']


def scrape(url):
    with semaphore:
        try:
            print(datetime.now(), url)
            if testing:
                with open('test.html', encoding=encoding) as tfile:
                    content = tfile.read()
            else:
                content = requests.get(url).content
            soup = BeautifulSoup(content, 'lxml')
            # print(soup)
            div = soup.find('div', {'id': 'hr_oHeader'})
            data = {'Link': url}
            for tr in div.find_all('tr'):
                tds = tr.find_all('td')
                for i in range(0, len(tds), 2):
                    data[tds[i].text.strip()] = tds[i + 1].text.replace('\n', ' ').strip()
            tree = html.fromstring(content)
            # data['Oglas'] = tree.xpath('//*[contains(text(),"Oglas")]/../following-sibling::div[1]')[0].text.replace('\n', ' ').strip()
            try:
                data['Oglas'] = soup.find('div', {'align': "justify"}).text.strip()
            except:
                pass
            pdfs = tree.xpath("//a[contains(@href,'pdf')]")
            for i in range(len(pdfs)):
                data[f'Datoteka {i + 1}'] = pdfs[i].text + " - " + pdfs[i].attrib['href'][2:]
            print(datetime.now(), json.dumps(data, indent=4))
            append(data)
        except:
            print("Error on", url)
            traceback.print_exc()
            with open(errorfile, 'a') as efile:
                efile.write(url + "\n")


def main():
    os.system('color 0a')
    logo()
    try:
        print('Press Ctrl+C to skip waiting...')
        wait_start('17:15')
    except KeyboardInterrupt:
        print('Waiting skipped...')
    # cvrt()
    # print(requests.post(licitacija, files={'file': open(logxl, 'rb')}))
    # input("Press any key...")
    if not os.path.isfile(outfile) or testing:
        with open(outfile, 'w', newline='', encoding=encoding) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
    with open(logfile, 'w', newline='', encoding=encoding) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
    if testing:
        scrape(
            f'{site}stecaj-ponude.aspx?Search=&Court=---&Type=False&Type1=False&Type2=False&Type3=&Manager=---&Status=N&P1=&ShowID=29171')
        return
    with open(outfile, 'r', encoding=encoding) as o:
        lines = o.read()
    # threading.Thread(target=csvtoxlsx).start()
    if os.path.isfile(errorfile):
        with open(errorfile, 'r') as efile:
            elines = efile.read().splitlines()
        if len(elines) > 0:
            print("Working on error file")
        for eline in elines:
            threading.Thread(target=scrape, args=(eline,)).start()
        print("Work on error file finished! now working on fresh data!")
    threads = []
    driver = getChromeDriver()
    driver.get(
        'http://www.sudacka-mreza.hr/stecaj-ponude.aspx?Search=&Court=---&Type=False&Type1=False&Type2=False&Type3=&Manager=---&Status=N&P1=')
    matches = driver.find_element_by_xpath('//span[@id="o_matchFound"]').text
    total = [int(s) for s in matches.split() if s.isdigit()][0]
    print("Total entries:", total)
    for i in range(1, int(total / 50) + 2):
        if i != 1:
            click(driver, f'//a[@title="{i}"]')
        for a in driver.find_elements_by_xpath('//a[@class="details"]'):
            url = a.get_attribute('href')
            if url not in lines:
                t = threading.Thread(target=scrape, args=(url,))
                threads.append(t)
                t.start()
                pass
            else:
                print("Already scraped", url)
    for thread in threads:
        thread.join()
    with lock:
        print("Converting to XLSX...")
        cvrt()
    print(requests.post(licitacija, files={'file': open(logxl, 'rb')}))


def cvrt():
    workbook = Workbook(logxl)
    worksheet = workbook.add_worksheet()
    with open(outfile, 'rt', encoding='utf8') as f:
        reader = csv.reader(f)
        for r, row in enumerate(reader):
            for c, col in enumerate(row):
                worksheet.write(r, c, col)
    workbook.close()


def append(row):
    global convert
    with lock:
        with open(outfile, 'a', newline='', encoding=encoding) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writerow(row)
        with open(logfile, 'a', newline='', encoding=encoding) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writerow(row)
        convert = True


def csvtoxlsx():
    global convert
    while True:
        if convert:
            with lock:
                print("Converting to XLSX...")
                cvrt()
            convert = False


def click(driver, xpath, js=False):
    if js:
        driver.execute_script("arguments[0].click();", getElement(driver, xpath))
    else:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()


def getElement(driver, xpath):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def sendkeys(driver, xpath, keys, js=False):
    if js:
        driver.execute_script(f"arguments[0].value='{keys}';", getElement(driver, xpath))
    else:
        getElement(driver, xpath).send_keys(keys)


def getChromeDriver(proxy=None):
    options = webdriver.ChromeOptions()
    if debug:
        # print("Connecting existing Chrome for debugging...")
        options.debugger_address = "127.0.0.1:9222"
    else:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
    if not images:
        # print("Turning off images to save bandwidth")
        options.add_argument("--blink-settings=imagesEnabled=false")
    if headless:
        # print("Going headless")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    if max:
        # print("Maximizing Chrome ")
        options.add_argument("--start-maximized")
    if proxy:
        # print(f"Adding proxy: {proxy}")
        options.add_argument(f"--proxy-server={proxy}")
    if incognito:
        # print("Going incognito")
        options.add_argument("--incognito")
    return webdriver.Chrome(options=options)


def getFirefoxDriver():
    options = webdriver.FirefoxOptions()
    if not images:
        # print("Turning off images to save bandwidth")
        options.set_preference("permissions.default.image", 2)
    if incognito:
        # print("Enabling incognito mode")
        options.set_preference("browser.privatebrowsing.autostart", True)
    if headless:
        # print("Hiding Firefox")
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
    return webdriver.Firefox(options)

def wait_start(runTime):
    startTime = time(*(map(int, runTime.split(':'))))
    while startTime > datetime.today().time():
        sleep(1)
        print(f"Waiting for {runTime}")


def logo():
    print(f"""
 __           _            _                                        
/ _\_   _  __| | __ _  ___| | ____ _        /\/\  _ __ ___ ______ _ 
\\ \| | | |/ _` |/ _` |/ __| |/ / _` |_____ /    \| '__/ _ \_  / _` |
_\ \ |_| | (_| | (_| | (__|   < (_| |_____/ /\/\ \ | |  __// / (_| |
\__/\__,_|\__,_|\__,_|\___|_|\_\__,_|     \/    \/_|  \___/___\__,_|

========================================================================
         www.sudacka-mreza.hr scraper by: fiverr.com/muhammadhassan7
========================================================================
[+] Multithreaded
[+] Resumeble
[+] Upload new logs to licitacija.hr
Threadcount: {threadcount}
""")


if __name__ == "__main__":
    main()
