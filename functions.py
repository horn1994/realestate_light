import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
import re
from geopy.geocoders import Nominatim
import numpy as np
import folium
import pandas as pd
import time

def load_settings():
    with open('settings.json', encoding='utf8') as f:
        settings = json.load(f)
    return settings

def get_html(
    settings,
    page_init = str(1),

):
    #Set vars
    url_init = settings['url_init']['url']
    user_agent = settings['scraper_user_agent']
    file_name = settings['file_name']
    filter_start = settings['url_init']['size_filter']['min']
    filter_end = settings['url_init']['size_filter']['max']
    filter_step = settings['url_init']['size_filter']['step']
    
    # Set up the browser
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Run the browser in headless mode (without GUI)
    #user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'
    options.add_argument(f'user-agent={user_agent}')
    
    driver=webdriver.Chrome(options=options)
    
    start = filter_start
    href_links_final = []
    
    while start < filter_end:
        try:
            driver=webdriver.Chrome(options=options)
            # Navigate to the URL
            url_filt = url_init.format(
                start,
                start+filter_step
            )+page_init
            driver.get(url_filt)

            # Get the HTML content
            #html_content = driver.page_source

            #Total number of pages
            pages =  driver.find_element('xpath','.//span[@class = "text-battleship"]').get_attribute("textContent")
            page_num = int(re.findall(r'\d+', pages)[0])

        finally:
            # Close the browser
            driver.quit()

        #link collector
        href_links_all = []

        for i in range(page_num): #page_num
            #Get updated url
            driver=webdriver.Chrome(options=options)
            url = url_init.format(
                start,
                start+filter_step
            )+ str(i+1)
            driver.get(url)

            #Links
            ids = driver.find_elements(by=By.XPATH, value="//a[@data-listing-id]")
            href_links = ["https://ingatlan.com/" + e.get_attribute("data-listing-id") for e in ids]
            href_links_all.extend(href_links)

            # Close the browser
            driver.quit()

            print(f"{i+1}/{page_num} is done")
        
        href_links_final.extend(href_links_all) 
        
        print(f'{url_init.format(start,start+filter_step)} finished')
        start+=filter_step 
    
    with open(r'{}'.format(file_name), 'w') as fp:
        for item in href_links_final:
            fp.write("%s\n" % item)
    

    return href_links_final

def parse_table(
    table_id, 
    data, 
    settings, 
    driver
):
    
    table_id = driver.find_element('xpath',f".//table[@class = '{settings['classes'][table_id]}']")
    rows = table_id.find_elements(By.TAG_NAME, "tr")

    for x in range(1, len(rows)):
        content = rows[x].get_attribute("textContent")
        lines = content.split('\n')
        cleaned_obj = [line.strip() for line in lines if line.strip()]
        try:
            data[cleaned_obj[0]] = float(cleaned_obj[1])
        except:
            data[cleaned_obj[0]] = cleaned_obj[1]
    return data

def scraper(
    settings
):
    
    #Scraping links
    all_links = get_html(
        settings = settings
    )
    
    #Reading original data if exists
    if os.path.exists(settings["data_file_name"]):
        print("Original data exists, comparing with new..")

        with open(settings["data_file_name"], encoding='utf8' ) as f:
            all_data = json.load(f)
        
        #Removing old data (urls deleted from website) from database
        curr_urls = []
        all_data_new = all_data.copy()
        
        for i,v in all_data.items():
            curr_urls.append(v['url'])
            
            if v['url'] not in all_links:
                all_data_new.pop(i, None)
        
        all_data = all_data_new.copy()
        
        #Keeping only new links to be scraped
        all_links = list(set(all_links) - set(curr_urls))
        
    else:
        all_data = {}
        
    # Set up the browser
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Run the browser in headless mode (without GUI)
    options.add_argument(f'user-agent={settings["scraper_user_agent"]}')


    #Scraping data from specific urls & saving to dictionary
    for i, _ in enumerate(all_links):
        # Set up the browser
        driver=webdriver.Chrome(options=options)
        driver.get(_)
        #html_content = driver.page_source
        
        #Basic info
        data = {'url': _}

        location = driver.find_element('xpath',f".//span[@class = '{settings['classes']['location']}']").get_attribute("textContent")
        data["Cím"] = location

        price_mill = driver.find_element('xpath',f".//div[@class = '{settings['classes']['price_mill']}']").get_attribute("textContent")
        price_mill =float(price_mill.split()[1].replace(',', '.'))
        data['Ár_millió']=  price_mill

        size = driver.find_element('xpath',f".//div[@class = '{settings['classes']['size']}']").get_attribute("textContent")
        size = float(re.findall(r'\d+', size)[0])
        data['Alapterület']=  size

        rooms = driver.find_element('xpath',f".//div[@class = '{settings['classes']['rooms']}']").get_attribute("textContent")
        rooms = rooms.split()[1]
        data['Szobák']=  float(rooms.replace(',', '.'))
        
        #Additional info
        data = parse_table(table_id = 'table1', data = data, settings = settings, driver = driver)
        data = parse_table(table_id = 'table2', data = data, settings = settings, driver = driver)
        all_data[str(time.time())] = data

        print(f'{i+1}/{len(all_links)} is done')

        driver.quit()
        
        if i // 500 == 0:
            save_file = open(settings['data_file_name'], "w", encoding='utf8')  
            json.dump(all_data, save_file, indent = 6, ensure_ascii=False)  
            save_file.close()  
        
    return all_data

def enrich_data(all_data):
    print("Enriching data with coordinates..")
    
    geolocator = Nominatim(user_agent="realestate-locator")
    
    for i,v in all_data.items():
        try:
            location = geolocator.geocode(v["Cím"])
            all_data[i]["Pontos_cím"] = location.address
            all_data[i]["Koordináták"] = (location.latitude, location.longitude)
        except AttributeError:
            all_data[i]["Pontos_cím"] = np.nan
            all_data[i]["Koordináták"] = np.nan
    
    return all_data

def create_map(settings):
    
    data = pd.read_json(settings['data_file_name']).T
    
    #Get scraping time
    data.reset_index(inplace = True)
    data.rename(columns={'index':'scrape_time'}, inplace = True)
    
    # Get data filters from settings
    filter_dict = settings['filters']

    # Use filter to reduce datasize
    for column, conditions in filter_dict.items():
        data = data[(data[column] >= conditions['min']) & (data[column] < conditions['max'])].copy()
    
    #Create map    
    m2 = folium.Map([47.5025527, 19.0321423], zoom_start=11.5)
    
    for i,row in data.iterrows():
        coordinates = row["Koordináták"]
        url = row['url']
        price = row["Ár_millió"]
        size = row["Alapterület"]
        rooms = row["Szobák"]
        scraping_time = row["scrape_time"]

        if coordinates is not None:
            iframe = folium.IFrame(
                f'''
                URL: <a href={url}>{url}</a><br> Price (mill): {price}<br> Size (m2): {size}<br> \
                Rooms (full-sized): {rooms}<br> Scraping time: {scraping_time}<br>
                '''
            )
            popup = folium.Popup(iframe,
                                 min_width=230,
                                 max_width=230)
            folium.Marker(
                location=row["Koordináták"],
                tooltip="Details",
                popup=popup,
                icon=folium.Icon(color="blue"),
            ).add_to(m2)

    return m2.save(settings["map_file_name"])