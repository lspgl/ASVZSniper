import urllib.request
import json
import datetime
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

FACILITIES = {'Höngg': '45598',
              'Irchel': '45577'}

SPORTS = {'Fitness': '122920'}


def main(timeslot, facility):
    assert facility in FACILITIES, f'Facility {facility} not in Facilities.'

    timetable_request = f'https://asvz.ch/asvz_api/event_search?f[0]=facility:{FACILITIES[facility]}&f[1]=sport:{SPORTS["Fitness"]}&availability=1&_format=json'
    response = urllib.request.urlopen(timetable_request).read()
    data = json.loads(response)

    if timeslot is None:
        print('No timeslot provided, enrolling for the next possible slot')
        entry = data['results'][0]

    else:
        timeslot = datetime.datetime.strptime(timeslot, '%Y.%m.%d-%H:%M')
        for _entry in data['results']:
            date = convert_asvz_time(_entry['from_date'])
            if date == timeslot:
                entry = _entry
                break
        else:
            raise Exception(f'Could not find any slots at {timeslot}')

    oe_date = convert_asvz_time(entry['oe_from_date'])
    entry_url = entry['url']
    places_free = entry['places_free']

    if places_free == 0:
        raise Exception(f'No more free slots at {timeslot}')

    driver = init_driver()
    ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)

    login_xpath = """/html/body/app-root/div/div[2]/app-lesson-details/div/div/app-lessons-enrollment-button/button"""
    try:
        driver.get(entry_url)
        WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.XPATH, login_xpath)))
        login_button = driver.find_element_by_xpath(login_xpath)
        title = login_button.get_attribute('title')
        if title != 'Login':
            raise NoSuchElementException
    except NoSuchElementException:
        pass
    else:
        driver.get('https://auth.asvz.ch/account/login')
        WebDriverWait(driver, 360).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#LoggedInUser")))
        print('Logged in!')
    finally:
        driver.close()

    now = datetime.datetime.now()
    print(f'Waiting for enrollment timeslot at {oe_date}')
    while now < oe_date - datetime.timedelta(seconds=3):
        now = datetime.datetime.now()

    driver = init_driver()
    driver.get(entry_url)
    WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#btnRegister')))
    enroll_button = driver.find_element_by_id('btnRegister')
    html = enroll_button.get_attribute('innerHTML')
    if 'ng-star-inserted' in html:
        print('Already enrolled')
    else:
        while True:
            now = datetime.datetime.now()
            print(f'Clicking at {now}')
            WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#btnRegister')))
            enroll_button = driver.find_element_by_id('btnRegister')
            enroll_button.click()
            WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#btnRegister')))
            enroll_button = driver.find_element_by_id('btnRegister')
            html = enroll_button.get_attribute('innerHTML')
            cls = enroll_button.get_attribute('class').split()

            if 'ng-star-inserted' in html:
                print('Succesfully Enrolled')
                break
            elif 'disabled' in cls:
                continue
            else:
                print('Oops, something went wrong')
                print(html)
                break
    driver.close()


def convert_asvz_time(time_str):
    dt_format = '%Y-%m-%dT%H:%M:%SZ'
    return datetime.datetime.strptime(time_str, dt_format).replace(tzinfo=datetime.timezone.utc).astimezone(tz=None).replace(tzinfo=None)


def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=chromeProfile")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.implicitly_wait(5)
    return driver


def parse():
    parser = argparse.ArgumentParser(description='ASVZ Enrollment Sniper')

    parser.add_argument('--slot',
                        help='Datetime of your desired slot in "YYYY.MM.DD-HH:MM "')

    parser.add_argument('--facility',
                        help='ASVZ Facility to enroll ("Höngg" or "Irchel")',
                        required=True)

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    parsed_args = parse()
    main(timeslot=parsed_args.slot, facility=parsed_args.facility)
