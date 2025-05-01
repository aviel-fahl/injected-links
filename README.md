# Web Link Injection Detector using Playwright

This Python script automates a web browser (Chromium) to navigate to a given URL and detect links (`<a>` tags with `href` attributes) that are dynamically injected into the page's DOM after the initial load, particularly on websites that use infinite scrolling or lazy loading.

It combines a real-time JavaScript `MutationObserver` injected into the page with a final scan of the Document Object Model (DOM) to identify links that weren't present when the page initially loaded.

This can be valuable knowledge when trying to improve performance on search engines and in LLMs, as injected links are often not detected by them.

## Features

- **Browser Automation:** Uses Playwright to control a real browser instance.
- **Infinite Scroll Handling:** Simulates user scrolling to trigger the loading of content that appears as the user scrolls down.
- **Real-time Detection:** Injects a `MutationObserver` script into the page to capture links as they are added to the DOM.
- **Final DOM Scan:** Performs a comprehensive scan of the entire accessible DOM at the end of the process as a backup mechanism.
- **Domain Filtering:** Allows specifying domains whose links should be ignored in the output.
- **Command-Line Interface:** Easy to run with a URL provided as an argument.
- **Detailed Output:** Provides live feedback on detected links and two final summaries.

## Requirements

- Python 3.7 or higher.
- `pip` package installer.
- Playwright browser binaries (Chromium by default).

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/aviel-fahl/injected-links.git
    cd injected-links
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Install Playwright browser binaries:**
    ```bash
    playwright install
    ```
    This command downloads the browser binaries needed by Playwright (Chromium, Firefox, WebKit - by default it installs all, but you only need Chromium for this script).

## Usage

Run the script from your terminal, providing the URL you want to scan as the first argument:

```bash
python injected_links.py <URL_TO_SCAN>
```

- Replace `<URL_TO_SCAN>` with the URL you want to scan.

If no URL is provided, the script defaults to `https://example.com`.

The script will launch a browser window (unless `headless=True` is set in the script), navigate to the URL, scroll, and print detected links to your console in real-time.

## Configuration

You can adjust several parameters by editing the Python script file directly, located near the top under configuration sections:

- `URL`: The default URL used if none is provided via command line.
- `IGNORE_DOMAINS`: A Python `set` of domain names (e.g., `"facebook.com"`) to exclude from the detected links.
- `SCROLL_STEP_PX`: The distance in pixels for each downward scroll movement.
- `SCROLL_PAUSE_SEC`: The pause duration in seconds between scroll steps to allow content to load.
- `SCROLL_STALLS`: The number of consecutive scroll attempts where the page's scroll height does _not_ increase before the script considers the page fully scrolled or done loading content via scrolling. Increase this for pages that load content in chunks with pauses.
- The final `page.wait_for_timeout(15_000)`: The duration (in milliseconds) the script waits after scrolling finishes. Adjust this if content loads significantly after the main scrolling activity.

## Output

The script provides two types of output:

1.  **Live Output:** As new links are detected by the injected `MutationObserver`, they are printed to the console prefixed with `[New Link Injected]`.

2.  **Final Summaries:** After the browser session completes, two JSON summaries are printed:

    - `=== ALL UNIQUE LINKS FOUND (Observer + Final Scan) ===`: This list contains all unique links (`<a href="...">`) found in the page's DOM that were accessible to the script at the very end of the scan, including those detected by the real-time observer AND those found by the final DOM scan. If no links were found by either method, it will indicate that.
    - `=== SUMMARY OF UNIQUE LINKS DETECTED AS INJECTED (Mutation Observer) ===`: This list contains the unique subset of links that were specifically captured by the `MutationObserver` as they were added to the DOM during the script's execution (after the observer was injected). This list is most relevant for identifying content _definitively_ injected dynamically via JavaScript after the initial load. If no links were detected by the observer, it will indicate that.

## Limitations

- **Inaccessible Iframes:** Due to browser security restrictions (Same-Origin Policy), the script **cannot** inject the `MutationObserver` or perform the final DOM scan within cross-origin iframes that do not explicitly allow scripting. Links injected _inside_ such iframes (common for ads or social media embeds) will **not** be detected by this script.
- **Link Format:** The script specifically looks for standard HTML `<a>` tags with an `href` attribute. It will **not** detect elements styled to look like links but implemented using other tags (like `<div>` or `<span>`) with JavaScript click handlers.
- **Site Variability:** The scrolling and waiting parameters (`SCROLL_STALLS`, pauses, final timeout) are heuristics. Some complex websites might require tuning these values for optimal detection.

## Contributing

Contributions are welcome\! If you find bugs or have ideas for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

## Acknowledgments

- Uses the excellent [Playwright](https://playwright.dev/) library for browser automation.
- Relies on the browser's native [MutationObserver API](https://developer.mozilla.org/en-US/docs/Web/API/MutationObserver).
- The core JavaScript `MutationObserver` snippet for real-time detection was inspired by or based on code shared by [Daniel Foley Carter](https://www.linkedin.com/in/daniel-foley-assertive/) on LinkedIn.

<!-- end list -->

```

```
