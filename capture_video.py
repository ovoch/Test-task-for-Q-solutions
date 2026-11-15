import argparse
import csv
from playwright.sync_api import sync_playwright
from qscript import CaptureVideo_Magento
from video_client import UploadVideo


def preview_video(video_url, view_seconds):
    with sync_playwright() as playwright:
        chromium = playwright.chromium
        browser = chromium.launch(headless = False)
        page = browser.new_page()
        page.goto(video_url)
        if view_seconds > 0:
            page.wait_for_timeout(view_seconds * 1000)
        else:
            input("Press Enter to close the browser...")
        browser.close()


def upload_and_preview(server, path, company_name, view_seconds):
    try:
        video_url = UploadVideo(server, path, company_name)
        print(f"Uploaded video URL: {video_url}")
        preview_video(video_url, view_seconds)
    except Exception as e:
        print(f"Upload or preview failed for {company_name}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default = None)
    parser.add_argument("--view-seconds", type = int, default = 5)
    args = parser.parse_args()

    with open("input.csv", newline = "", encoding = "utf-8-sig") as csvfile:
        dict_to_run = csv.DictReader(csvfile, delimiter = ";", quotechar = '"')
        for row in dict_to_run:
            path = CaptureVideo_Magento(
                row["URL"],
                row["Company Name"],
                row["Language"],
                row["Country"],
                row["Postcode"],
                row["City"],
                row["Street"],
                row["HouseNo"],
            )
            print(f"Saved video: {path}")
            if path and args.server:
                upload_and_preview(args.server, path, row["Company Name"], args.view_seconds)


main()