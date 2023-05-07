# research-gpt


### Selenium Setup

To set up Selenium with Chrome's headless mode in your WSL2 Ubuntu environment, follow these steps:

1. Install Google Chrome in your WSL2 environment:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

2. Install ChromeDriver:
```bash
wget https://chromedriver.storage.googleapis.com/94.0.4606.61/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```
Make sure to replace the URL with the latest version of ChromeDriver that matches your installed Google Chrome version. You can find the latest ChromeDriver releases at https://sites.google.com/a/chromium.org/chromedriver/downloads.

3. Install the required Python packages in your virtual environment:
```bash
# Activate your virtual environment
source /path/to/your/venv/bin/activate

# Install selenium
pip install selenium
```

4. You may need to install additional dependencies for Selenium and Chrome to work correctly in your WSL2 environment:
```bash
sudo apt-get install -y libx11-xcb1 libxkbcommon0 libxtst6 libxss1 libgbm1
```

After completing these steps, you should be able to use Selenium with Chrome's headless mode in your WSL2 environment. The provided `fetch_html` function in my previous response should work as expected.