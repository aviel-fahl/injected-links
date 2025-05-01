"""
Playwright Script to Detect Dynamically Injected Links

This script navigates to a given URL, simulates scrolling to the bottom
to trigger lazy loading, and uses a MutationObserver injected into the page
to detect new <a> elements with href attributes that are added to the DOM
after the initial page load. It also performs a final DOM scan to catch
any links present at the end state that might have been missed by the
real-time observer. Links from specified ignore domains are filtered.
"""

import sys
import json
import time
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

# --- Configuration -----------------------------------------------------------

# URL to navigate to. Reads from command line argument or uses example.com as default.
URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

# Domains to ignore when reporting injected links (e.g., common social media trackers).
IGNORE_DOMAINS = {
    "facebook.com", "www.facebook.com",
    "twitter.com",  "www.twitter.com",
    "linkedin.com", "www.linkedin.com",
    # Add more domains as needed
}

# --- Scrolling Configuration -------------------------------------------------

# How far to scroll down in each step (pixels). Approx. half a typical viewport.
SCROLL_STEP_PX = 600
# Pause duration between scroll steps (seconds) to allow content to load.
SCROLL_PAUSE_SEC = 0.25
# Number of consecutive scroll attempts where the document height doesn't change
# before considering the page fully scrolled/loaded (for infinite scroll).
# More stalls may provide for better robustness on some sites.
SCROLL_STALLS = 7

# --- Injected JavaScript Mutation Observer -----------------------------------

# JavaScript snippet based on a share by Daniel Foley Carter (https://www.linkedin.com/in/daniel-foley-assertive/) on LinkedIn.
# This script is injected into the browser context to listen for DOM changes.
MUTATION_OBSERVER_JS = """
(() => {
  // Create a new MutationObserver instance.
  new MutationObserver(mutations => {
    // Iterate over each detected mutation.
    for (const m of mutations) {
      // Check newly added nodes in the mutation.
      for (const node of m.addedNodes) {
        // Only process element nodes (nodeType 1).
        if (node.nodeType !== 1) continue;

        // Helper function to visit a node and its descendants.
        const visit = el => {
          // Check if the current element is an <a> tag with an href.
          if (el.tagName === 'A' && el.href) {
            console.log('[New Link Injected]', el.href);
          }
          // Check for <a> tags with href within the element's descendants.
          // Use ?. for optional chaining in case querySelectorAll is not available (e.g., text nodes, though filtered).
          el.querySelectorAll?.('a[href]').forEach(link => {
            console.log('[New Link Injected]', link.href);
          });
        };
        // Start visiting from the added node.
        visit(node);
      }
    }
  }).observe(document.body, {
    childList: true, // Observe direct children additions/removals.
    subtree: true    // Observe changes in the entire subtree of the body.
  });
})();
"""

# --- Main Script Logic -------------------------------------------------------


def main():
    """
    Main function to run the link injection detection process.
    Sets up Playwright, navigates, injects observer, scrolls,
    waits, performs a final scan, and reports findings.
    """
    # List to store links detected by the MutationObserver console logs.
    injected_links = []

    # Context manager for Playwright.
    with sync_playwright() as p:
        # Launch a Chromium browser instance.
        # headless=False allows watching the automation (set to True for production).
        # slow_mo adds a delay for debugging/demonstration.
        # args can potentially help with certain site behaviors but not a universal fix for iframes.
        browser = p.chromium.launch(
            headless=False, slow_mo=50, args=["--disable-features=IsolateOrigins,site-per-process"])
        page = browser.new_page()
        # Set a fixed viewport size.
        page.set_viewport_size({"width": 1400, "height": 900})

        # --- Console Message Handling ---

        # Define a handler function for console messages from the page.
        def handle_console(msg):
            # Check if the message type is 'log' and starts with our prefix.
            if msg.type == "log" and msg.text.startswith("[New Link Injected]"):
                # Extract the URL from the log message.
                # example: "[New Link Injected] https://evil.example/bad"
                try:
                    _, href = msg.text.split("] ", 1)
                    # Parse the URL to get the domain.
                    domain = urlparse(href).netloc.lower()
                    # Ignore links from specified domains.
                    if domain in IGNORE_DOMAINS:
                        return
                    # Add the link to our list if not ignored.
                    injected_links.append(href)
                    # Print the detected link to standard output for live feedback.
                    print(msg.text)
                except ValueError:
                    # Handle cases where the console message format is unexpected.
                    print(
                        f"[Warning] Could not parse console message: {msg.text}")

        # Register the handler for console messages.
        page.on("console", handle_console)

        # --- Navigation and Initialization ---

        # Navigate to the target URL.
        # wait_until="domcontentloaded" waits for the initial HTML to be parsed.
        # "networkidle" can also be used but might wait too long on some sites.
        page.goto(URL, wait_until="domcontentloaded")

        # Inject the MutationObserver script into all accessible frames.
        inject_observer_into_all_frames(page, MUTATION_OBSERVER_JS)

        # Wait for network activity to calm down after initial load.
        page.wait_for_load_state("networkidle")

        # --- Scrolling to Trigger Lazy Loading ---

        # Simulate scrolling to the end of the page.
        wheel_scroll_to_bottom(page, verbose=True)

        # --- Final Waiting Period ---

        # Add an extra cushion to allow debounced loaders or final async
        # content to appear after scrolling finishes. This is crucial for
        # some sites.
        print(f"\nWaiting {15_000/1000} seconds for final content...")
        page.wait_for_timeout(15_000)  # Wait in milliseconds.

        # --- Final DOM Scan ---

        # Perform a scan of the entire accessible DOM at the end.
        # This catches links found by the observer and any others present
        # at the end state in accessible frames, providing a more complete picture.
        print("\n=== Performing final DOM scan ===")
        all_present_links = set()
        # Iterate through all frames Playwright can access.
        for frame in page.frames:
            try:
                # Evaluate JavaScript in the frame to find all <a> elements with hrefs.
                links_in_frame = frame.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href]')).map(link => link.href);
                }""")
                # Process found links.
                for href in links_in_frame:
                    # Ignore links from specified domains.
                    domain = urlparse(href).netloc.lower()
                    if domain not in IGNORE_DOMAINS:
                        all_present_links.add(href)
            except Exception as e:
                # Catch exceptions (e.g., cross-origin frames where scripting is blocked).
                # These frames cannot be scanned using this method.
                # print(f"Could not scan frame {frame.name}: {e}") # Optional: uncomment for debugging skipped frames
                pass

        # Combine links found by the observer and the final scan.
        # Using a set ensures uniqueness.
        combined_links = sorted(
            list(set(injected_links).union(all_present_links)))

        # --- Reporting: Combined Summary ---

        # Print a summary of all unique links found by either the observer or the final scan.
        print("\n=== ALL UNIQUE LINKS FOUND (Observer + Final Scan) ===")
        # Check if the combined list is empty for cleaner output.
        if not combined_links:
            print(
                "[Info] No unique links found by either detection method in accessible frames.")
        else:
            print(json.dumps(combined_links, indent=2))

        # --- Cleanup ---

        # Close the browser instance and shut down Playwright.
        browser.close()

    # --- Reporting: Injected Links Summary ---

     # After the browser is closed and Playwright context is exited,
    # process and print the links that were specifically captured
    # by the MutationObserver during DOM changes. These are the links
    # most likely to have been "injected" dynamically *after* initial load.
    # This list is a subset of the combined list, focusing only on links
    # whose addition was observed in real-time.
    dup_free_injected = sorted(set(injected_links))

    # Print a summary only if injected links were found by the observer.
    if not dup_free_injected:
        print(
            "\n[Good News!] No links specifically detected as injected by the Mutation Observer.")
    else:
        print("\n=== SUMMARY OF UNIQUE LINKS DETECTED AS INJECTED (Mutation Observer) ===")
        print(json.dumps(dup_free_injected, indent=2))


# --- Helper Functions --------------------------------------------------------

def wheel_scroll_to_bottom(page, *, verbose: bool = True):
    """
    Scrolls downward in SCROLL_STEP_PX increments until the document height
    stops growing for SCROLL_STALLS consecutive iterations.
    Uses mouse wheel events to simulate user interaction more closely.
    Works for classic pages and most 'infinite scroll' implementations.

    Args:
        page: The Playwright Page object.
        verbose: If True, print progress during scrolling.
    """
    stalls = 0
    # Get the initial scroll height of the document body.
    last_height = page.evaluate("() => document.body.scrollHeight")
    step_counter = 0  # Counter for scroll steps.

    if verbose:
        print(f"[wheel] start – initial docHeight={last_height}")

    # Loop while the number of "stalled" scroll attempts is less than the threshold.
    # A stall occurs when scrolling doesn't increase the document height.
    while stalls < SCROLL_STALLS:
        # Perform one incremental scroll downward using the mouse wheel.
        page.mouse.wheel(0, SCROLL_STEP_PX)
        # Pause to allow potential new content to load and the DOM to update.
        time.sleep(SCROLL_PAUSE_SEC)
        step_counter += 1

        # Read the new state: the current scroll height after the scroll step.
        new_height = page.evaluate("() => document.body.scrollHeight")
        # Get current scroll position for logging
        curr_y = page.evaluate("() => window.scrollY")

        # Log the movement and state if verbose.
        if verbose:
            print(f"[wheel] step {step_counter:02d} – y={curr_y}, "
                  f"current docHeight={new_height}, stalls={stalls}")

        # Decide whether we made progress: Has the document height increased since the last check?
        if new_height == last_height:
            # If the height hasn't changed, increment the stall counter.
            stalls += 1
        else:
            # If the height *has* changed, content was likely loaded. Reset the stall counter.
            stalls = 0
            # Update the last recorded height to the new height.
            last_height = new_height

        # Optional check: Stop if we are visually at the very bottom and height isn't changing
        # This handles cases where scrollHeight might not perfectly reflect the visual end.
        # is_at_visual_bottom = page.evaluate(
        #     "() => window.scrollY + window.innerHeight >= document.body.scrollHeight")
        # if is_at_visual_bottom and new_height == last_height:
        #     # If at the visual bottom and height isn't changing, count this as a stall too.
        #     # This might cause it to finish scrolling slightly sooner on some pages.
        #     stalls += 1

    if verbose:
        # Get the final scroll position and height for the final log message.
        curr_y = page.evaluate("() => window.scrollY")
        last_height = page.evaluate("() => document.body.scrollHeight")
        print(f"[wheel] finished after {step_counter} steps – "
              f"final y={curr_y}, final docHeight={last_height}")


def inject_observer_into_all_frames(page, observer_js):
    """
    Injects the given JavaScript code (expected to be a MutationObserver setup)
    into the main frame and all accessible sub-frames of a Playwright page.
    Accessible frames are typically same-origin or those with permissive CSP/COOP.

    Args:
        page: The Playwright Page object.
        observer_js: A string containing the JavaScript code to inject.
    """
    # Iterate through all frames known to Playwright for this page.
    for frame in page.frames:
        try:
            # Attempt to evaluate/inject the script into the frame.
            frame.evaluate(observer_js)
            # print(f"Injected observer into frame: {frame.name} (URL: {frame.url})") # Optional: for debugging
        except Exception as e:
            # If injection fails (most commonly due to cross-origin restrictions or CSP),
            # catch the exception and skip this frame. These frames cannot be observed
            # using this method.
            # print(f"Could not inject observer into frame {frame.name} (URL: {frame.url}): {e}") # Optional: for debugging skipped frames
            pass


# --- Script Entry Point ------------------------------------------------------

if __name__ == "__main__":
    main()
