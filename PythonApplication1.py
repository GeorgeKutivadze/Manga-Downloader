import os
from unittest import skip
import requests
from bs4 import BeautifulSoup
import re
from io import BytesIO
from zipfile import ZipFile
from tqdm import tqdm
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import webbrowser
import time
import stat
import random
from PIL import Image, UnidentifiedImageError
import logging
import pyautogui


# Base directory for manga storage
base_dir = r"C:\Users\gokag.DESKTOP-Q55650I\Downloads"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36",
    "Referer": "",
}

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def clean_title_for_search(title):
    return re.sub(r"[^\w\s]", "", title).strip().replace(" ", "+")

def log_error(manga_dir, error_message):
    error_log_path = os.path.join(manga_dir, "error_log.txt")
    with open(error_log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().isoformat()} - {error_message}\n")
    print(f"Error logged to {error_log_path}")

def save_html_as_txt(manga_dir, html_content):
    html_file_path = os.path.join(manga_dir, "page_content.txt")
    with open(html_file_path, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)
    return html_file_path

def extract_alternative_titles_from_file(manga_dir):
    page_content_path = os.path.join(manga_dir, "page_content.txt")
    
    if not os.path.exists(page_content_path):
        print(f"page_content.txt not found in {manga_dir}")
        return []

    # Read the content of the page_content.txt file
    with open(page_content_path, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Parse the HTML to extract alternative titles
    soup = BeautifulSoup(html_content, 'html.parser')
    alternative_titles_tag = soup.find('td', class_='table-label')
    
    if alternative_titles_tag and 'Alternative' in alternative_titles_tag.text:
        alternative_titles_value = alternative_titles_tag.find_next_sibling('td', class_='table-value')
        
        if alternative_titles_value:
            titles_text = alternative_titles_value.find('h2').text
            alternative_titles = [title.strip() for title in titles_text.split(';')]
            return alternative_titles

    print("No alternative titles found in page_content.txt.")
    return []

def save_url(manga_dir, url):
    url_file_path = os.path.join(manga_dir, "url.txt")
    with open(url_file_path, "w", encoding="utf-8") as url_file:
        url_file.write(url)
    print(f"URL saved to {url_file_path}")

def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")  # Simulate a maximized window
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass Selenium automation detection
    chrome_options.add_argument("--disable-extensions")  # Disable extensions
    chrome_options.add_argument("--disable-gpu")  # Disable GPU for better compatibility
    chrome_options.add_argument("--incognito")  # Use incognito mode to prevent tracking
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # Start Chrome with the necessary options
    chrome_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    # Set a custom user-agent to mimic a real browser
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36"
    })

    return driver

def human_like_interaction(driver):
    time.sleep(random.uniform(2, 5))  # Random delay between 2-5 seconds
    
    # Simulate scrolling
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1, 3))
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(2, 5))

def download_image(img_url, save_dir, save_name, max_retries=3):
    """Download image with retry mechanism."""
    save_path = os.path.join(save_dir, save_name)
    retries = 0

    while retries < max_retries:
        try:
            session = requests.Session()
            # Set default headers, customize as needed
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
            })
            
            with session.get(img_url, stream=True, timeout=10) as img_response:
                img_response.raise_for_status()

                with open(save_path, 'wb') as img_file:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            img_file.write(chunk)
            
            print(f"Image successfully downloaded and saved at: {save_path}")
            return True
        
        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"Attempt {retries} failed: {e}. Retrying...")
            time.sleep(2)
    
    print(f"Failed to download image after {max_retries} attempts.")
    return False

def download_cover_from_mangadex(manga_title, manga_dir):
    """Attempt to download the cover image from MangaDex using Selenium."""
    driver = init_selenium()
    try:
        search_url = f"https://mangadex.org/search?q={manga_title.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(3)  # Allow time for page load

        first_manga_card = driver.find_element(By.CSS_SELECTOR, 'div.grid.gap-2 img.rounded.shadow-md')
        if first_manga_card:
            cover_img_url = first_manga_card.get_attribute('src')
            return download_image(cover_img_url, manga_dir, 'cover.jpg')

        print(f"No cover image found for {manga_title} on MangaDex.")
        return False

    except Exception as e:
        print(f"Error downloading cover from MangaDex: {e}")
        return False

    finally:
        driver.quit()

def search_using_alternative_titles(manga_title, manga_dir, alt_site_url):
    """Search for alternative titles and attempt to download cover image using them."""
    try:
        response = requests.get(alt_site_url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching alternative titles from {alt_site_url}: {e}")
        return False

    alternative_titles = extract_alternative_titles(html_content)

    if alternative_titles:
        print(f"Alternative titles found: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True
    print(f"Failed to download cover image using alternative titles.")
    return False

def extract_alternative_titles(html_content):
    """Extract alternative manga titles from the HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    alternative_titles_tag = soup.find('td', class_='table-label', string='Alternative')

    if alternative_titles_tag:
        alternative_titles_value = alternative_titles_tag.find_next_sibling('td', class_='table-value')
        if alternative_titles_value:
            titles_text = alternative_titles_value.get_text(separator=';')
            alternative_titles = [title.strip() for title in titles_text.split(';') if title.strip()]
            return alternative_titles

    return []

def search_using_alternative_titles(manga_title, manga_dir, alt_site_url):
    # Download and parse the alternative website HTML
    try:
        html_content = requests.get(alt_site_url, headers=headers).text
    except requests.exceptions.RequestException as e:
        print(f"Failed to access {alt_site_url}: {e}")
        return False

    alternative_titles = extract_alternative_titles(html_content)

    if alternative_titles:
        print(f"Alternative titles found: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True

    print("Failed to download cover image using alternative titles.")
    return False

def search_mangadex_and_download_cover_selenium(manga_title, manga_dir, alt_site_url):
    driver = None  # Initialize driver to None for better exception handling
    try:
        driver = init_selenium()  # Initialize Selenium driver
        cleaned_title = clean_title_for_search(manga_title)
        search_url = f"https://mangadex.org/search?q={cleaned_title}"
        print(f"Searching for {manga_title} on MangaDex using Selenium: {search_url}")
        
        driver.get(search_url)
        human_like_interaction(driver)  # Simulate human behavior on the page

        # Try to find the first manga card that has an image
        first_manga_card = driver.find_element(By.CSS_SELECTOR, 'div.grid.gap-2 img.rounded.shadow-md')
        if not first_manga_card:
            print(f"No results found on MangaDex for {manga_title}. Falling back to alternative titles...")
            return search_using_alternative_titles_from_file(manga_title, manga_dir)

        # Get the cover image URL
        cover_img_url = first_manga_card.get_attribute('src')
        print(f"Found cover image via Selenium: {cover_img_url}")

        # Download and save the image using Selenium
        driver.get(cover_img_url)
        time.sleep(2)  # Wait for the image to fully load
        save_path = os.path.join(manga_dir, "cover.jpg")

        # Save the image as a screenshot
        with open(save_path, "wb") as file:
            file.write(driver.find_element(By.TAG_NAME, "img").screenshot_as_png)

        print(f"Image downloaded and saved at: {save_path}")
        return True

    except Exception as e:
        log_error(manga_dir, f"Error searching or downloading cover using Selenium: {e}")
        # Fall back to alternative titles if there was an error
        return search_using_alternative_titles_from_file(manga_title, manga_dir)

    finally:
        if driver:
            driver.quit()  

def search_using_alternative_titles_from_file(manga_title, manga_dir):
    alternative_titles = extract_alternative_titles_from_file(manga_dir)

    if alternative_titles:
        print(f"Alternative titles found in page_content.txt: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True

    print("Failed to download cover image using alternative titles.")
    return False

def extract_and_download_cover(manga_dir, html_file_path, base_url, manga_title, alt_site_url):
    success = search_mangadex_and_download_cover_selenium(manga_title, manga_dir, alt_site_url)  # Use Selenium-based search
    if success:
        return

    print("Falling back to original method to download cover image.")
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    cover_img_tag = soup.select_one('div.panel-story-info div.story-info-left img.img-loading')
    
    if not cover_img_tag or not cover_img_tag.get('src'):
        log_error(manga_dir, "Cover image tag not found or missing 'src' attribute.")
        return

    cover_img_url = urljoin(base_url, cover_img_tag['src'])
    download_image(cover_img_url, manga_dir, "cover.jpg")





def switch_server(driver, server_number):
    server_buttons = driver.find_elements(By.CLASS_NAME, 'server-image-btn')
    if server_buttons and len(server_buttons) >= server_number:
        server_buttons[server_number - 1].click()
        time.sleep(2)  # Wait for page to load
    else:
        print(f"Failed to switch to server {server_number}")

def download_image_convert(img_url, save_dir, save_name):
    save_path = os.path.join(save_dir, save_name)
    try:
        img_response = requests.get(img_url, headers=headers, stream=True, timeout=10)
        img_response.raise_for_status()  # Ensure the request was successful

        # Check if the response is an image by inspecting the Content-Type header
        content_type = img_response.headers.get('Content-Type')
        if 'image' not in content_type:
            print(f"URL did not return an image: {img_url}, Content-Type: {content_type}")
            return False

        # Try opening the image to check if it's valid
        try:
            img = Image.open(BytesIO(img_response.content))
        except UnidentifiedImageError as e:
            print(f"Failed to identify image at URL: {img_url}, error: {e}")
            return False

        # Convert image to JPG if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(save_path, "JPEG")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Failed to download/convert image: {img_url}, error: {e}")
        return False

def validate_image(img_path):
    try:
        img = Image.open(img_path)
        img.verify()  # Verify if image is valid
        return True
    except Exception as e:
        print(f"Image validation failed: {img_path}, error: {e}")
        os.remove(img_path)  # Remove corrupt image
        return False
total_download_size2 = 0
def download_chapter_images(chapter_url, manga_title, chapter_title, manga_dir):

    global total_download_size2
    """
    Download chapter images with a fallback mechanism. 
    If downloading fails from both servers, switch to download_manga2 for recovery.
    """
    # Initialize Selenium driver
    driver = init_selenium()
    driver.get(chapter_url)

    chapter_images = []
    download_successful = False

    # Try downloading from both servers (server 1 and server 2)
    for server_number in range(1, 3):
        print(f"\n Trying server {server_number}...")
        if server_number > 1:
            switch_server(driver, server_number)

        try:
            # Wait for images to appear using WebDriverWait
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.container-chapter-reader img'))
            )

            # Find images using Selenium
            image_elements = driver.find_elements(By.CSS_SELECTOR, 'div.container-chapter-reader img')
            if not image_elements:
                print(f"No images found on server {server_number}.")
                continue  # Retry with the next server if no images found

            # Calculate the total size of all images (for the progress bar)
            total_size = 0
            image_sizes = {}  # To track each image's size
            for img_elem in image_elements:
                try:
                    img_url = img_elem.get_attribute('src')
                    img_head = requests.head(img_url, headers=headers)
                    if 'Content-Length' in img_head.headers:
                        img_size = int(img_head.headers['Content-Length'])
                        image_sizes[img_url] = img_size
                        total_size += img_size
                    else:
                        print(f"Could not get size for image {img_url}")
                except StaleElementReferenceException:
                    print(f"Stale element reference for image. Retrying image collection.")
                    image_elements = driver.find_elements(By.CSS_SELECTOR, 'div.container-chapter-reader img')
                    img_elem = image_elements[image_elements.index(img_elem)]
                    img_url = img_elem.get_attribute('src')
                    img_head = requests.head(img_url, headers=headers)
                    if 'Content-Length' in img_head.headers:
                        img_size = int(img_head.headers['Content-Length'])
                        image_sizes[img_url] = img_size
                        total_size += img_size

            # Initialize the progress bar
            progress = tqdm(total=total_size, desc=f"Downloading {chapter_title}", unit="B", unit_scale=True)
            
            total_download_size2 += total_size

            # Download images with a progress bar
            for idx, img_elem in enumerate(image_elements, start=1):
                retries = 3  # Retry mechanism for each image download
                while retries > 0:
                    try:
                        img_url = img_elem.get_attribute('src')
                        save_name = f"{idx:03}.jpg"
                        save_path = os.path.join(manga_dir, save_name)

                        # Download and convert the image to JPG
                        if download_image_convert(img_url, manga_dir, save_name):
                            if validate_image(save_path):
                                chapter_images.append(save_path)

                                # Update the progress bar
                                if img_url in image_sizes:
                                    progress.update(image_sizes[img_url])
                                else:
                                    # Fallback size if not available
                                    progress.update(os.path.getsize(save_path))
                                break  # Exit retry loop if download is successful

                        retries -= 1  # Decrement retry counter if download fails

                    except StaleElementReferenceException:
                        print(f"Stale element reference for image {idx}. Retrying image download.")
                        # Re-locate image elements and retry
                        image_elements = driver.find_elements(By.CSS_SELECTOR, 'div.container-chapter-reader img')
                        img_elem = image_elements[idx-1]  # Re-fetch the same image element
                        retries -= 1  # Decrement retry counter

                if retries == 0:
                    print(f"Failed to download image {idx} after 3 retries. Skipping.")

                # If the first image fails, switch servers immediately
                if idx == 1 and not os.path.exists(save_path):
                    print(f"First image failed. Switching server immediately.")
                    progress.close()
                    break  # Stop and switch to the next server

            progress.close()
            
            # If images were successfully downloaded, create a CBZ file
            if chapter_images:
                create_cbz_file(manga_title, chapter_title, manga_dir, chapter_images)
                delete_downloaded_images(chapter_images)# Clean up images after CBZ creation
                download_successful = True  # Mark download as successful
                break # Exit server loop after successful download
                return
            
        except TimeoutException:  # Handle timeout exception
            print(f"Timed out waiting for images on server {server_number}. Retrying with the next server.")

    driver.quit()
 
def create_cbz_file(manga_title, chapter_title, manga_dir, chapter_images):
    cbz_name = f"{manga_title} {chapter_title.strip()}.cbz"
    cbz_path = os.path.join(manga_dir, cbz_name)

    if os.path.exists(cbz_path) and os.path.getsize(cbz_path) == 0:
        print(f"Removing empty CBZ file: {cbz_path}")
        os.remove(cbz_path)

    with ZipFile(cbz_path, 'w') as cbz_file:
        for image in chapter_images:
            cbz_file.write(image, os.path.basename(image))
    
    print(f"CBZ file created: {cbz_path}")

    # Ensure images are deleted after the CBZ file is created
    delete_downloaded_images(chapter_images)

def wait_for_cbz_files(manga_dir, timeout=20, interval=5):
    

    start_time = time.time()
    
    while True:
        all_stable = True
        for filename in os.listdir(manga_dir):
            if filename.endswith(".cbz"):
                cbz_path = os.path.join(manga_dir, filename)
                initial_size = os.path.getsize(cbz_path)
                
                # Wait for a short interval and check if the file size changes
                time.sleep(interval)
                new_size = os.path.getsize(cbz_path)
                
                # If the file size has changed, it's still being loaded
                if initial_size != new_size:
                    print(f"File {filename} is still being loaded. Waiting...")
                    all_stable = False
                    break
        
        # If all files are stable, break out of the loop
        if all_stable:
            print("All .cbz files have been loaded successfully.")
            break
        
        # Check if we have exceeded the timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            print(f"Timeout of {timeout} seconds exceeded. Proceeding anyway.")
            break

def delete_downloaded_images(images):
    for image in images:
        os.remove(image)
    print("Chapter images deleted after CBZ creation.")

def close_chrome_like_human():
    """
    Simulates human-like behavior to close Chrome by sending the Ctrl+W (or Command+W on macOS) keyboard shortcut.
    """
    print("Simulating human-like Chrome closure...")
    
    # Adding a delay to mimic human pause before action
    time.sleep(2)

    # Simulate pressing Ctrl+W to close the active Chrome tab (Command+W for macOS)
    pyautogui.hotkey('ctrl', 'w')

    print("Chrome tab closed like a human!")

def download_manga_chapter(url, manga_title, chapter_title, manga_dir):
    """
    Downloads a manga chapter. If the browser is closed unexpectedly or fails, it handles the exception and moves to the next chapter.
    Automatically closes the browser after downloading or skipping the chapter.
    """
    print(f"Downloading chapter: {chapter_title}")

    # Check if the CBZ file for the specific chapter already exists and is valid
    cbz_name = f"{manga_title} {chapter_title.strip()}.cbz"
    cbz_path = os.path.join(manga_dir, cbz_name)

    # Skip download if file already exists
    if os.path.exists(cbz_path) and os.path.getsize(cbz_path) > 0:
        close_chrome_like_human()
        print(f"Chapter {chapter_title} already exists as {cbz_path}. Skipping download.")
        """!!!"""
        return  # Skip the download, no need to initialize the driver

    # Initialize Selenium driver after file check
    driver = None  # Initialize the driver variable

    try:
        # Initialize the driver only if the download is needed
        driver = init_selenium()
        driver.get(url)
        download_successful = False

        # Try downloading from both server 1 and server 2
        for server_number in range(1, 3):
            print(f"\nTrying server {server_number}...")
            if server_number > 1:
                switch_server(driver, server_number)

            try:
                # Wait for the images to load using WebDriverWait
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.container-chapter-reader img'))
                )

                # Download chapter images
                download_chapter_images(url, manga_title, chapter_title, manga_dir)
                download_successful = True
                break  # Exit loop if successful download

            except TimeoutException:
                print(f"Timed out waiting for images on server {server_number}. Retrying with the next server.")
            except StaleElementReferenceException:
                print(f"Stale element reference error. Retrying.")
            except WebDriverException as e:
                print(f"WebDriverException: {e}. Browser might have been closed.")
                break  # Exit server loop and move to next chapter

        if not download_successful:
            print(f"Both servers failed for chapter {chapter_title}. Switching to download_manga2.")
            download_manga2(url, manga_title, chapter_title, manga_dir)

    except WebDriverException as e:
        print(f"Error occurred: {e}. Moving to next chapter.")  # Handle browser closure/crash

    finally:
        # Ensure driver is properly closed after each chapter
        if driver is not None:
            close_chrome_like_human()

    print(f"Finished downloading chapter {chapter_title}")

def download_manga2(url, manga_title, specific_chapter):
    manga_dir = os.path.join(base_dir, manga_title)
    log_file_path = os.path.join(manga_dir, "download_log.txt")

    # Check if the CBZ file for the specific chapter already exists and is valid
    cbz_name_without_dash = f"{manga_title} {specific_chapter.strip()}.cbz"
    cbz_path_without_dash = os.path.join(manga_dir, cbz_name_without_dash)

    if os.path.exists(cbz_path_without_dash) and os.path.getsize(cbz_path_without_dash) > 0:

        log_file_path = os.path.join(manga_dir, "download_log.txt")
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{url}\t{specific_chapter}\t{datetime.now().isoformat()}\n")

        print(f"TRY2 Chapter {specific_chapter} already exists as {cbz_path_without_dash}. Skipping download.")
        return  # Skip download

    # Iterate over chapters and download only missing ones
    for chapter_item in url:

        cbz_name_without_dash = f"{manga_title} {specific_chapter.strip()}.cbz"  # File without dash
        bz_path_without_dash = os.path.join(manga_dir, cbz_name_without_dash)

        if os.path.exists(bz_path_without_dash) and os.path.getsize(bz_path_without_dash) > 0:
            print(f"This Chapter already exists, EXITING: {specific_chapter} | URL: {url}")
            return

        print(f"Processing fallback chapter: {specific_chapter} | URL: {url}")
        
        # Perform the download process for each chapter
        download_chapter_images(url, manga_title, specific_chapter, manga_dir)


        # Log the download in the log file
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{url}\t{specific_chapter}\t{datetime.now().isoformat()}\n")

        print(f"Successfully processed and logged chapter {specific_chapter}. Exiting download_manga2 and continuing with the next chapter.")
    return

def update_manga2(chapter_url, manga_title, specific_chapter):

    manga_dir = os.path.join(base_dir, manga_title)
    log_file_path = os.path.join(manga_dir, "download_log.txt")

    # Check if the CBZ file for the specific chapter already exists and is valid
    cbz_name_without_dash = f"{manga_title} {specific_chapter.strip()}.cbz"
    cbz_path_without_dash = os.path.join(manga_dir, cbz_name_without_dash)

    if os.path.exists(cbz_path_without_dash) and os.path.getsize(cbz_path_without_dash) > 0:
        print(f"Chapter {specific_chapter} already exists as {cbz_path_without_dash}. Skipping update.")
        return  # Skip update

    print(f"Processing fallback for chapter: {specific_chapter} | URL: {chapter_url}")

    try:
        # Attempt to download the chapter images
        download_chapter_images(chapter_url, manga_title, specific_chapter, manga_dir)

        # Perform the download process for each chapter
        cbz_name = f"{manga_title} {specific_chapter.strip()}.cbz"
        cbz_path = os.path.join(manga_dir, cbz_name)
        if os.path.exists(cbz_path) and os.path.getsize(cbz_path) == 0:
            return

        # Log the update in the log file
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"{chapter_url}\t{specific_chapter}\t{datetime.now().isoformat()}\n")

        print(f"Successfully processed and logged chapter {specific_chapter}.")
        return

    except Exception as e:
        cbz_name = f"{manga_title} {specific_chapter.strip()}.cbz"
        cbz_path = os.path.join(manga_dir, cbz_name)

        # Skip download if file already exists
        if os.path.exists(cbz_path) and os.path.getsize(cbz_path) > 0:
            print(f"Chapter {specific_chapter} already exists as {cbz_path}. Skipping download.")
            return
            
        else:
            print(f"Failed to update chapter {specific_chapter}: {e}")
            print(f"Falling back to download_manga2 for chapter {specific_chapter}.")

            # Call download_manga2 to handle the failure
            download_manga2(chapter_url, manga_title, specific_chapter)
            return






def download_manga(url, manga_title=None):
    """
    Main function to download manga chapters. If image download fails, switches to download_manga2 to handle the failed chapter.
    """
    headers['Referer'] = url
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the manga page. Error: {e}")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    if not manga_title:
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Processing Manga: {manga_title}")
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)
    os.makedirs(manga_dir, exist_ok=True)
    
    # Save URL and HTML content if not already saved
    save_url(manga_dir, url)
    html_file_path = save_html_as_txt(manga_dir, html_content)
    print(f"HTML content saved to {html_file_path}")

    # Extract and download cover with alternative titles
    alt_site_url = "https://manganelo.com/manga-hero-x-demon-queen"
    extract_and_download_cover(manga_dir, html_file_path, url, manga_title, alt_site_url)

    # Process chapters
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")

        cbz_name_already_exists = f"{manga_title} {chapter_title.strip()}.cbz"
        if os.path.exists(cbz_name_already_exists) and os.path.getsize(cbz_name_already_exists) > 0:
            continue
        
        
        try:
            chapter_response = requests.get(chapter_url, headers=headers)
            chapter_response.raise_for_status()
            chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

            image_container = chapter_soup.find('div', class_='container-chapter-reader')
            
            if image_container:
                image_tags = image_container.find_all('img', class_=['reader-content', 'img-content'])
                
                if not image_tags:
                    print(f"No images found in chapter: {chapter_title}. Skipping...")
                    continue
                
                print(f"Found {len(image_tags)} images in chapter: {chapter_title}")

                # Estimate download size
                chapter_size = 0
                for img_tag in image_tags:
                    img_url = img_tag['src']
                    img_head = requests.head(img_url, headers=headers)
                    if 'Content-Length' in img_head.headers:
                        size = int(img_head.headers['Content-Length'])
                        chapter_size += size

                total_download_size += chapter_size

                print(f"Estimated size for {chapter_title}: {chapter_size / (1024 * 1024):.2f} MB")

                with BytesIO() as img_data:
                    with ZipFile(img_data, 'w') as cbz_file:
                        progress = tqdm(total=chapter_size, desc=f"Downloading {chapter_title}", unit="B", unit_scale=True)
                        for i, img_tag in enumerate(image_tags):
                            img_url = img_tag['src']
                            img_response = requests.get(img_url, headers=headers)
                            if img_response.status_code == 200:
                                img_name = f"{i+1:03}.jpg"
                                cbz_file.writestr(img_name, img_response.content)
                                progress.update(len(img_response.content))
                            else:
                                # If the first image fails, switch to download_manga2
                                if i == 0:
                                    print(f"Failed to download the first image of {chapter_title}. Switching to alternative method.")
                                    download_manga2(chapter_url, manga_title, specific_chapter=chapter_title)
                                    break
                                else:
                                    print(f"Failed to download image {img_url}, skipping it.")
                                    continue
                        progress.close()

                    # Extract chapter number using regex
                    match = re.search(r'Chapter (\d+(\.\d+)?)', chapter_title)
                    if match:
                        chapter_number = match.group(1)
                        if '.' in chapter_number:
                            chapter_number = chapter_number.replace('.', 'p')
                        else:
                            chapter_number = f"{int(chapter_number):02}"

                        cbz_filename = f"{manga_title} Chapter {chapter_number}.cbz"
                        cbz_path = os.path.join(manga_dir, cbz_filename)

                        with open(cbz_path, 'wb') as file:
                            file.write(img_data.getvalue())
                        
                        with open(log_file_path, "a", encoding="utf-8") as log_file:
                            log_file.write(f"{chapter_url}\t{chapter_title}\t{datetime.now().isoformat()}\n")
                    else:
                        print(f"Failed to extract chapter number from title '{chapter_title}'. Skipping...")
            else:
                print(f"Could not find image container for chapter: {chapter_title}. Skipping...")

        except Exception as e:
            print(f"Error processing chapter {chapter_title}: {e}")
            print(f"Switching to alternative method for chapter: {chapter_title}")
            download_manga2(chapter_url, manga_title, specific_chapter=chapter_title)
    
    total_download_size_in_mb = (total_download_size + total_download_size2) / (1024 * 1024)
    print(f"Total estimated download size: {total_download_size_in_mb:.2f} MB")
    update_combined_log()

def update_combined_log():
    combined_log_path = os.path.join(base_dir, "combined_download_log.txt")

    with open(combined_log_path, "w", encoding="utf-8") as combined_log:
        combined_log.write(f"{'Manga Title':<30} {'Total Chapters':<15} {'Last Updated':<25}\n")
        combined_log.write("="*70 + "\n")
        
        for manga_folder in os.listdir(base_dir):
            manga_path = os.path.join(base_dir, manga_folder)
            if os.path.isdir(manga_path):
                log_file = os.path.join(manga_path, "download_log.txt")
                
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as individual_log:
                        chapters = individual_log.readlines()
                        if chapters:
                            last_updated = chapters[-1].strip().split("\t")[-1]
                            combined_log.write(f"{manga_folder:<30} {len(chapters):<15} {last_updated:<25}\n")

def list_manga_folders():
    manga_folders = [folder for folder in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, folder))]
    print("Available Manga Titles:")
    for index, folder in enumerate(manga_folders, 1):
        print(f"{index}. {folder}")
    return manga_folders

def select_and_update_folders():
    manga_folders = list_manga_folders()
    print("Enter 'all' to update all folders.")
    selected_numbers = input("Enter the numbers of the manga folders to update (comma-separated): ").split(',')
    
    if 'all' in selected_numbers:
        selected_numbers = range(1, len(manga_folders) + 1)
    else:
        selected_numbers = [int(num.strip()) for num in selected_numbers]

    for num in selected_numbers:
        if 1 <= num <= len(manga_folders):
            manga_folder = manga_folders[num-1]
            manga_folder_path = os.path.join(base_dir, manga_folder)
            url_file_path = os.path.join(manga_folder_path, "url.txt")

            if os.path.exists(url_file_path):
                with open(url_file_path, "r", encoding="utf-8") as url_file:
                    manga_page_url = url_file.read().strip()
                print(f"Updating folder: {manga_folder}")
                update_manga(manga_page_url, manga_title=manga_folder)
            else:
                print(f"URL file missing for folder '{manga_folder}'. Please enter the URL.")
                new_url = input(f"Enter the URL for '{manga_folder}': ").strip()
                save_url(manga_folder_path, new_url)
                update_manga(new_url, manga_title=manga_folder)
        else:
            print(f"Invalid selection: {num}. Skipping...")

def update_manga(url, manga_title=None):
    """
    Main function to download manga chapters. If the first image download fails,
    it switches to update_manga2 to handle the specific chapter.
    """
    headers['Referer'] = url
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html_content = response.text

    if not manga_title:
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Updating Manga: {manga_title}")

    # Sanitize the manga title
    manga_title = sanitize_filename(manga_title)
    manga_dir = os.path.join(base_dir, manga_title)

    soup = BeautifulSoup(html_content, 'html.parser')
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                parts = line.strip().split("\t")
                if len(parts) == 3:
                    chapter_url, chapter_title, last_updated = parts
                    existing_log[chapter_url] = (chapter_title, last_updated)
                else:
                    print(f"Skipping invalid log entry: {line.strip()}")

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")

        chapter_response = requests.get(chapter_url, headers=headers)
        chapter_response.raise_for_status()
        chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

        image_container = chapter_soup.find('div', class_='container-chapter-reader')

        if image_container:
            image_tags = image_container.find_all('img', class_=['reader-content', 'img-content'])

            if not image_tags:
                print(f"No images found in chapter: {chapter_title}. Skipping...")
                continue

            print(f"Found {len(image_tags)} images in chapter: {chapter_title}")

            # Estimate download size
            chapter_size = 0
            for img_tag in image_tags:
                img_url = img_tag['src']
                img_head = requests.head(img_url, headers=headers)
                if 'Content-Length' in img_head.headers:
                    size = int(img_head.headers['Content-Length'])
                    chapter_size += size

            total_download_size += chapter_size

            print(f"Estimated size for {chapter_title}: {chapter_size / (1024 * 1024):.2f} MB")

            with BytesIO() as img_data:
                with ZipFile(img_data, 'w') as cbz_file:
                    progress = tqdm(total=chapter_size, desc=f"Downloading {chapter_title}", unit="B", unit_scale=True)

                    for i, img_tag in enumerate(image_tags):
                        img_url = img_tag['src']
                        img_response = requests.get(img_url, headers=headers)

                        # Check if the first image fails and switch to update_manga2
                        if img_response.status_code != 200 and i == 0:
                            print(f"\nFailed to download the first image of {chapter_title}. Switching to update_manga2.")
                            progress.close()
                            update_manga2(chapter_url, manga_title, chapter_title)  # Pass correct chapter URL
                            break  # Exit the current function to prevent further execution
                        
                        if img_response.status_code == 200:
                            img_name = f"{i+1:03}.jpg"
                            cbz_file.writestr(img_name, img_response.content)
                            progress.update(len(img_response.content))
                        else:
                            print(f"Failed to download image {img_url}")
                    progress.close()

                # Extract chapter number using regex
                match = re.search(r'Chapter (\d+(\.\d+)?)', chapter_title)
                if match:
                    chapter_number = match.group(1)
                    if '.' in chapter_number:
                        chapter_number = chapter_number.replace('.', 'p')
                    else:
                        chapter_number = f"{int(chapter_number):02}"

                    cbz_filename = f"{manga_title} Chapter {chapter_number}.cbz"
                    cbz_path = os.path.join(manga_dir, cbz_filename)


                    if not os.path.exists(cbz_path):
                        with open(cbz_path, 'wb') as file:
                            file.write(img_data.getvalue())

                    # Log the successful download
                    with open(log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"{chapter_url}\t{chapter_title}\t{datetime.now().isoformat()}\n")

                    print(f"Successfully processed and logged chapter: {chapter_title}")

                else:
                    print(f"Failed to extract chapter number from title '{chapter_title}'. Skipping...")

            # Continue to the next chapter
            print(f"Moving to the next chapter after {chapter_title}...\n")

        else:
            print(f"Could not find image container for chapter: {chapter_title}. Skipping...")

    total_download_size_in_mb = (total_download_size + total_download_size2) / (1024 * 1024)
    print(f"Total estimated download size: {total_download_size_in_mb:.2f} MB")
    update_combined_log()


user_input = input("Enter the manga page URL or 'update' to select folders for update: ")

if user_input.lower() == 'update':
    select_and_update_folders()
else:
    download_manga(user_input)

print(f"All selected chapters downloaded and saved in their respective directories.")
print(f"Combined log file updated and saved at {os.path.join(base_dir, 'combined_download_log.txt')}")

input("Press Enter to exit...") 