from functions import load_settings, get_html, parse_table, scraper, enrich_data, create_map
import json

if __name__ == "__main__":
    settings = load_settings()

    all_data = scraper(
        settings = settings
    )

    all_data = enrich_data(
        all_data = all_data
        )

    save_file = open(settings['data_file_name'], "w", encoding='utf8')  
    json.dump(all_data, save_file, indent = 6, ensure_ascii=False)  
    save_file.close()