
from functions import load_settings, create_map

if __name__ == "__main__":

    settings = load_settings()

    #This will need additional filtering if we want to show all (e.g. within price range)
    create_map(
        settings = settings
    )