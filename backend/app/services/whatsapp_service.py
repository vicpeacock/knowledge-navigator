from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import pywhatkit as pwt
import platform
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp integration using Python libraries"""
    
    def __init__(self):
        self.driver = None
        self.is_authenticated = False
        # Use a completely isolated profile that won't interfere with user's Chrome
        # Store in a temp-like directory that's clearly separate
        self.default_profile_path = Path.home() / ".whatsapp_selenium_profile"
        # Allow resetting profile if needed
        self._profile_reset = False
    
    def _get_chrome_options(self, headless: bool = False, profile_path: Optional[str] = None):
        """Get Chrome options with proper configuration for macOS/Linux"""
        options = webdriver.ChromeOptions()
        
        # Use isolated profile that won't interfere with user's Chrome
        final_profile_path = profile_path or str(self.default_profile_path)
        if not headless:  # Only use persistent profile if not headless
            # Ensure profile directory exists
            Path(final_profile_path).mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={final_profile_path}")
            # Use a separate profile name to completely isolate it
            options.add_argument(f"--profile-directory=WhatsAppSelenium")
            logger.info(f"Using isolated WhatsApp profile: {final_profile_path}/WhatsAppSelenium")
        
        # Basic options
        if headless:
            options.add_argument("--headless=new")  # Use new headless mode
        else:
            # Non-headless: show window for QR code scanning
            # Use a specific window title to identify it
            options.add_argument("--window-size=1280,800")
            options.add_argument("--start-maximized")
            # Add a unique window name so it's clearly separate
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        
        # Security and stability options (essential for macOS)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Try to avoid detection - use less aggressive options
        # Don't disable AutomationControlled completely - might break things
        # options.add_argument("--disable-blink-features=AutomationControlled")
        
        # macOS specific options
        if platform.system() == "Darwin":  # macOS
            # Try without VizDisplayCompositor disable - might be causing rendering issues
            # options.add_argument("--disable-features=VizDisplayCompositor")
            # Important: exclude automation flags to avoid detection
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            # Disable GPU in headless mode on macOS
            if headless:
                options.add_argument("--disable-gpu")
        
        # Windows/Linux options
        if platform.system() == "Windows":
            options.add_argument("--disable-features=VizDisplayCompositor")
            if headless:
                options.add_argument("--disable-gpu")
        
        # Remote debugging only if needed (can cause conflicts)
        # options.add_argument("--remote-debugging-port=9222")
        
        # Prefs for better WhatsApp Web compatibility
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1,
        }
        options.add_experimental_option("prefs", prefs)
        
        return options
    
    def _check_authentication_status(self) -> Dict[str, Any]:
        """Check if WhatsApp Web is authenticated"""
        if not self.driver:
            return {"authenticated": False, "status": "no_driver", "message": "WhatsApp Web not initialized"}
        
        try:
            # Get current URL to check if we're on WhatsApp Web
            current_url = self.driver.current_url
            if "web.whatsapp.com" not in current_url:
                # Navigate to WhatsApp Web if not already there
                try:
                    self.driver.get("https://web.whatsapp.com")
                    import time
                    time.sleep(2)  # Wait for page to load
                except Exception as e:
                    logger.warning(f"Could not navigate to WhatsApp Web: {e}")
            
            # Check for chat list (authenticated) - multiple selectors
            auth_selectors = [
                "[data-testid='chat-list']",
                "[data-testid='conversation-list']",
                "#side",  # Main sidebar
                "[role='grid']",  # Chat grid
            ]
            
            for selector in auth_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.info(f"Found authenticated element: {selector}")
                        self.is_authenticated = True
                        return {"authenticated": True, "status": "authenticated", "message": "WhatsApp Web is authenticated"}
                except NoSuchElementException:
                    continue
            
            # Check for QR code (not authenticated) - multiple selectors
            qr_selectors = [
                "[data-ref]",
                "canvas",  # QR code canvas
                "[data-testid='qr-code']",
            ]
            
            for selector in qr_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        logger.info(f"Found QR code element: {selector}")
                        self.is_authenticated = False
                        return {"authenticated": False, "status": "qr_code_visible", "message": "Please scan QR code"}
                except NoSuchElementException:
                    continue
            
            # Check page source for keywords
            page_source = self.driver.page_source.lower()
            if "qr" in page_source or "scan" in page_source:
                if "code" in page_source or "whatsapp" in page_source:
                    return {"authenticated": False, "status": "qr_code_visible", "message": "QR code detected - please scan"}
            
            # If we can't find QR code but also can't find chat list, check if page is loaded
            if "web.whatsapp.com" in current_url:
                # Try to find any chat elements
                try:
                    # Look for any chat-related elements
                    any_chat = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid*='chat'], [data-testid*='conversation'], [role='listitem']")
                    if any_chat:
                        logger.info("Found chat elements - likely authenticated")
                        self.is_authenticated = True
                        return {"authenticated": True, "status": "authenticated", "message": "WhatsApp Web appears to be authenticated"}
                except:
                    pass
            
            # If we have a driver and we're on WhatsApp Web, assume authenticated if no QR code found
            if "web.whatsapp.com" in current_url:
                logger.info("On WhatsApp Web, no QR code found - assuming authenticated")
                self.is_authenticated = True
                return {"authenticated": True, "status": "authenticated", "message": "WhatsApp Web appears to be authenticated"}
            
            # Unknown state
            return {"authenticated": False, "status": "unknown", "message": "Could not determine authentication status"}
            
        except Exception as e:
            logger.error(f"Error checking authentication status: {e}", exc_info=True)
            return {"authenticated": False, "status": "error", "message": str(e)}
    
    async def setup_whatsapp_web(
        self,
        headless: bool = False,
        profile_path: Optional[str] = None,
        wait_for_auth: bool = True,
        timeout: int = 120,
    ):
        """
        Setup WhatsApp Web using Selenium
        
        Args:
            headless: Run browser in headless mode (not recommended for first setup)
            profile_path: Custom profile path for persistent sessions
            wait_for_auth: If True, wait for QR code scan. If False, return immediately after opening.
            timeout: Maximum time to wait for authentication (seconds)
        """
        try:
            # Close existing session if any
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                self.is_authenticated = False
            
            # If profile reset is needed, clear the profile directory
            if self._profile_reset:
                import shutil
                profile_path_to_clear = profile_path or str(self.default_profile_path)
                if Path(profile_path_to_clear).exists():
                    try:
                        shutil.rmtree(profile_path_to_clear)
                        logger.info(f"Cleared WhatsApp profile: {profile_path_to_clear}")
                    except Exception as e:
                        logger.warning(f"Could not clear profile: {e}")
                self._profile_reset = False
            
            # Note: If Chrome is already open manually with WhatsApp Web,
            # we'll use the same profile and Chrome should open already authenticated
            
            options = self._get_chrome_options(headless=headless, profile_path=profile_path)
            
            # Important: Use a fixed remote debugging port for WhatsApp Selenium
            # This prevents conflicts and makes it clear this is Selenium-controlled
            debug_port = 9223
            options.add_argument(f"--remote-debugging-port={debug_port}")
            # Add app name to make it clear this is WhatsApp automation
            options.add_argument("--app-name=WhatsApp-Selenium")
            
            # Try to create Chrome driver using webdriver-manager for automatic ChromeDriver management
            # Use thread executor to avoid blocking event loop
            import asyncio
            import concurrent.futures
            
            try:
                logger.info("Initializing Chrome driver with webdriver-manager...")
                logger.info(f"Using profile: {profile_path or self.default_profile_path}")
                logger.info(f"Debug port: {debug_port}")
                
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    # Run ChromeDriverManager.install() in thread
                    try:
                        driver_path = await asyncio.wait_for(
                            loop.run_in_executor(executor, ChromeDriverManager().install),
                            timeout=10.0  # Short timeout
                        )
                        service = Service(driver_path)
                        # Run Chrome() in thread too
                        self.driver = await asyncio.wait_for(
                            loop.run_in_executor(executor, lambda: webdriver.Chrome(service=service, options=options)),
                            timeout=15.0  # Increased timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning("ChromeDriver initialization timed out")
                        raise Exception("ChromeDriver initialization timed out. Please close Chrome if it's already open and try again.")
                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(f"Failed with webdriver-manager: {error_msg}")
                        
                        # Check if error is about Chrome already running
                        if "instance exited" in error_msg.lower() or "chrome instance" in error_msg.lower():
                            raise Exception(
                                "Chrome is already running with this profile. "
                                "Please close all Chrome windows and try again, or use a different profile."
                            )
                        
                        # Fallback: try without service
                        try:
                            logger.info("Trying fallback: ChromeDriver from PATH")
                            self.driver = await asyncio.wait_for(
                                loop.run_in_executor(executor, lambda: webdriver.Chrome(options=options)),
                                timeout=15.0
                            )
                        except Exception as e2:
                            error_msg2 = str(e2)
                            if "instance exited" in error_msg2.lower():
                                raise Exception(
                                    "Chrome is already running. Please close all Chrome windows and try again."
                                )
                            logger.error(f"Fallback also failed: {e2}")
                            raise Exception(f"ChromeDriver failed: {error_msg2}")
                            
            except Exception as e:
                logger.error(f"ChromeDriver initialization error: {e}")
                error_str = str(e)
                if "instance exited" in error_str.lower():
                    raise Exception(
                        "Cannot start Chrome: Chrome is already running with this profile. "
                        "Please close all Chrome windows and try again."
                    )
                raise Exception(f"ChromeDriver initialization failed: {error_str}")
            
            logger.info("Chrome driver initialized successfully")
            
            # Navigate to WhatsApp Web
            logger.info("Navigating to WhatsApp Web...")
            try:
                self.driver.get("https://web.whatsapp.com")
                logger.info(f"Navigated to WhatsApp Web. Current URL: {self.driver.current_url}")
                
                # Wait a bit for page to load
                time.sleep(3)
                
                # Verify we're actually on WhatsApp Web
                current_url = self.driver.current_url
                if "web.whatsapp.com" not in current_url:
                    logger.warning(f"Not on WhatsApp Web! Current URL: {current_url}")
                    # Try to navigate again
                    self.driver.get("https://web.whatsapp.com")
                    time.sleep(2)
            except Exception as nav_error:
                logger.error(f"Error navigating to WhatsApp Web: {nav_error}", exc_info=True)
                raise Exception(f"Failed to navigate to WhatsApp Web: {str(nav_error)}")
            
            # Wait a bit more for page to fully load
            time.sleep(2)
            
            # Wait for WhatsApp Web to fully initialize - check for JavaScript errors
            logger.info("Waiting for WhatsApp Web to fully initialize...")
            try:
                # Wait for the main app to be ready
                WebDriverWait(self.driver, 20).until(
                    lambda driver: driver.execute_script(
                        "return window.Store && typeof window.Store !== 'undefined'"
                    )
                )
                logger.info("WhatsApp Web Store is ready")
            except TimeoutException:
                logger.warning("WhatsApp Web Store not ready, but continuing...")
                # Check for JavaScript errors
                try:
                    logs = self.driver.get_log('browser')
                    errors = [log for log in logs if log['level'] == 'SEVERE']
                    if errors:
                        logger.warning(f"JavaScript errors found: {errors[:3]}")  # Log first 3 errors
                except:
                    pass
            
            # Additional wait for chats to load and render
            logger.info("Waiting for WhatsApp Web to render chats...")
            time.sleep(8)  # Give WhatsApp more time to load and render chats
            
            # Try to trigger a scroll or interaction to help rendering
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, 100);")
                time.sleep(1)
            except:
                pass
            
            # Check initial status
            try:
                status = self._check_authentication_status()
                logger.info(f"Initial authentication status: {status}")
            except Exception as status_error:
                logger.warning(f"Error checking initial status: {status_error}")
                status = {"authenticated": False, "status": "checking"}
            
            if status.get("authenticated"):
                logger.info("WhatsApp Web already authenticated (using existing session)")
                self.is_authenticated = True
                return {
                    "success": True,
                    "message": "WhatsApp Web is authenticated and ready",
                    "authenticated": True,
                }
            
            if not wait_for_auth:
                # Return immediately - user can scan QR code manually
                logger.info("Setup complete. Waiting for user to scan QR code...")
                # Don't block - return immediately
                return {
                    "success": True,
                    "message": "WhatsApp Web opened. Please scan the QR code with your phone if needed. Use 'Verifica Stato' button to check authentication.",
                    "authenticated": False,
                    "status": status.get("status", "waiting_for_qr_scan"),
                }
            
            # Wait for authentication with polling (only if wait_for_auth is True)
            logger.info(f"Waiting for QR code scan (timeout: {timeout}s)...")
            start_time = time.time()
            poll_interval = 2  # Check every 2 seconds
            max_polls = timeout // poll_interval  # Limit polling iterations
            
            for i in range(max_polls):
                status = self._check_authentication_status()
                
                if status["authenticated"]:
                    logger.info("WhatsApp Web authenticated successfully!")
                    self.is_authenticated = True
                    return {
                        "success": True,
                        "message": "WhatsApp Web authenticated successfully",
                        "authenticated": True,
                    }
                
                # Log progress every 10 seconds
                elapsed = int(time.time() - start_time)
                if elapsed > 0 and elapsed % 10 == 0:
                    logger.info(f"Still waiting for authentication... ({elapsed}s elapsed)")
                
                # Use asyncio.sleep instead of time.sleep to avoid blocking
                import asyncio
                await asyncio.sleep(poll_interval)
            
            # Timeout reached - don't raise error, just return status
            status = self._check_authentication_status()
            logger.warning(f"Timeout reached. Status: {status}")
            return {
                "success": True,
                "message": f"Timeout waiting for authentication. Current status: {status.get('status')}. Use /status endpoint to check later.",
                "authenticated": False,
                "status": status.get("status", "timeout"),
            }
                    
        except Exception as e:
            logger.error(f"Error setting up WhatsApp Web: {e}", exc_info=True)
            # Clean up driver if it was created
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                self.is_authenticated = False
            raise Exception(f"Error setting up WhatsApp: {str(e)}")
    
    async def get_recent_messages(
        self,
        contact_name: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent WhatsApp messages"""
        if not self.driver:
            raise ValueError("WhatsApp Web driver not initialized. Please setup first.")
        
        # Check authentication status
        status = self._check_authentication_status()
        if not status["authenticated"]:
            raise ValueError(
                f"WhatsApp Web not authenticated. Status: {status.get('status')}. "
                f"Message: {status.get('message', 'Please scan QR code')}"
            )
        
        self.is_authenticated = True  # Update status
        
        messages = []
        
        try:
            # Ensure we're on WhatsApp Web
            current_url = self.driver.current_url
            if "web.whatsapp.com" not in current_url:
                logger.info("Navigating to WhatsApp Web...")
                self.driver.get("https://web.whatsapp.com")
                time.sleep(3)  # Wait for page load
            
            # Wait for WhatsApp Web to fully load (wait for chat list to appear)
            logger.info("Waiting for WhatsApp Web to fully load...")
            try:
                # Wait for the main chat list container to be visible
                WebDriverWait(self.driver, 15).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#pane-side")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-item']")),
                    )
                )
                logger.info("WhatsApp Web loaded successfully")
                time.sleep(2)  # Additional wait for animations
            except TimeoutException:
                logger.warning("Chat list not found, but continuing anyway...")
            
            if contact_name:
                # Search for contact
                logger.info(f"Searching for contact: {contact_name}")
                try:
                    # Try multiple selectors for search box
                    search_selectors = [
                        "[data-testid='chat-search-input']",
                        "div[contenteditable='true'][data-tab='3']",
                        "div[contenteditable='true'][role='textbox']",
                        "input[type='text']",
                    ]
                    
                    search_box = None
                    for selector in search_selectors:
                        try:
                            search_box = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            if search_box:
                                break
                        except TimeoutException:
                            continue
                    
                    if not search_box:
                        logger.warning("Could not find search box")
                    else:
                        # Click on search box to focus
                        search_box.click()
                        time.sleep(1)
                        # Type contact name
                        if search_box.tag_name == "div":
                            # Contenteditable div
                            search_box.send_keys(contact_name)
                        else:
                            # Input field
                            search_box.clear()
                            search_box.send_keys(contact_name)
                        time.sleep(3)  # Wait for search results
                        
                        # Click on first result
                        first_result = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='chat-item']"))
                        )
                        first_result.click()
                        time.sleep(3)  # Wait for chat to open
                except (TimeoutException, NoSuchElementException) as e:
                    logger.warning(f"Could not find contact '{contact_name}': {e}")
                    # Continue to get messages from current chat
            else:
                # Get messages from the first chat in the list (most recent)
                logger.info("Opening first chat in list...")
                try:
                    # Wait longer for chat list to be fully loaded and visible
                    logger.info("Waiting for chat list to be visible...")
                    time.sleep(2)  # Give WhatsApp time to render
                    
                    # Try multiple selectors for chat items
                    chat_selectors = [
                        "[data-testid='chat-item']",
                        "div[role='listitem']",
                        "div._8nE1Y",
                        "div[data-testid='list-item']",
                    ]
                    
                    first_chat = None
                    for selector in chat_selectors:
                        try:
                            # Wait for elements to be present and visible
                            chats = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            # Filter for visible chats
                            visible_chats = [c for c in chats if c.is_displayed()]
                            if visible_chats:
                                first_chat = visible_chats[0]
                                logger.info(f"Found {len(visible_chats)} visible chats using selector: {selector}")
                                break
                        except TimeoutException:
                            continue
                        except Exception as e:
                            logger.debug(f"Error with selector {selector}: {e}")
                            continue
                    
                    if first_chat:
                        # Scroll to make sure chat is visible
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_chat)
                            time.sleep(1)
                        except:
                            pass
                        
                        first_chat.click()
                        logger.info("First chat clicked")
                        # Wait longer for chat to fully open and messages to be visible
                        time.sleep(5)  # Increased wait time for messages to appear
                        
                        # Force a refresh/wait for message area to be ready
                        try:
                            # Try to find message area to confirm chat opened
                            WebDriverWait(self.driver, 10).until(
                                EC.any_of(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "#main")),
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='application']")),
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='conversation-panel-messages']")),
                                )
                            )
                            logger.info("Chat opened and message area is ready")
                        except TimeoutException:
                            logger.warning("Message area not found, but continuing...")
                    else:
                        logger.warning("Could not find any chat items")
                        return []
                except Exception as e:
                    logger.warning(f"Could not open chat: {e}")
                    return []
            
            # Get messages from active chat
            logger.info("Extracting messages from active chat...")
            try:
                # Wait for message container/panel to be visible
                # WhatsApp Web uses a scrollable container for messages
                message_panel_selectors = [
                    "#main",
                    "[role='application']",
                    "[data-testid='conversation-panel-messages']",
                    "div[role='log']",
                ]
                
                message_panel = None
                for selector in message_panel_selectors:
                    try:
                        panel = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if panel:
                            message_panel = panel
                            logger.info(f"Found message panel using selector: {selector}")
                            break
                    except TimeoutException:
                        continue
                
                if not message_panel:
                    logger.warning("Message panel not found, trying to find messages directly...")
                else:
                    # Scroll up to load more messages (WhatsApp loads messages dynamically)
                    logger.info("Scrolling up to load more messages...")
                    try:
                        # Scroll up multiple times to load older messages
                        for scroll_attempt in range(3):
                            self.driver.execute_script(
                                "arguments[0].scrollTop = 0;",
                                message_panel
                            )
                            time.sleep(1)  # Wait for messages to load
                            logger.info(f"Scroll attempt {scroll_attempt + 1}/3")
                        
                        # Scroll back down a bit to ensure we're in a good position
                        time.sleep(1)
                        self.driver.execute_script(
                            "arguments[0].scrollTop = arguments[0].scrollHeight / 4;",
                            message_panel
                        )
                        time.sleep(1)
                    except Exception as e:
                        logger.warning(f"Error scrolling message panel: {e}")
                
                # Now find all message elements
                message_selectors = [
                    "[data-testid='msg-container']",
                    "[data-testid='message-container']",
                    "div[data-id]",
                    "div.message",
                    "span.selectable-text",
                ]
                
                message_elements = []
                for selector in message_selectors:
                    try:
                        elements = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        if elements:
                            message_elements = elements
                            logger.info(f"Found {len(elements)} message elements using selector: {selector}")
                            break
                    except TimeoutException:
                        continue
                
                # If still no elements, try a more general approach
                if not message_elements:
                    logger.info("Trying alternative approach to find messages...")
                    try:
                        # Look for any div with text content in the message area
                        all_divs = self.driver.find_elements(By.CSS_SELECTOR, "#main div, [role='application'] div")
                        # Filter for divs that look like messages (have text, not just empty containers)
                        for div in all_divs:
                            try:
                                text = div.text.strip()
                                if text and len(text) > 5:  # Skip very short texts
                                    # Check if it's not a UI element (has certain classes or attributes)
                                    classes = div.get_attribute("class") or ""
                                    if "message" in classes.lower() or "text" in classes.lower():
                                        message_elements.append(div)
                            except:
                                continue
                        if message_elements:
                            logger.info(f"Found {len(message_elements)} messages using alternative approach")
                    except Exception as e:
                        logger.warning(f"Alternative approach failed: {e}")
                
                if not message_elements:
                    logger.warning("No message elements found")
                    return []
                
                # Extract text from messages with metadata
                from datetime import datetime
                today = datetime.now().date()
                
                for elem in message_elements[-max_results*2:]:  # Get more to filter by date
                    try:
                        # Try different selectors for message text
                        text = None
                        for text_selector in [
                            "[data-testid='message-text']",
                            "span.selectable-text",
                            ".message-text",
                            "span._11JPr",
                            "div.selectable-text",
                        ]:
                            try:
                                text_elem = elem.find_element(By.CSS_SELECTOR, text_selector)
                                text = text_elem.text.strip()
                                if text:
                                    break
                            except NoSuchElementException:
                                continue
                        
                        # If no text found, try getting text directly from element
                        if not text:
                            text = elem.text.strip()
                        
                        if not text or len(text) < 3:  # Skip very short texts
                            continue
                        
                        # Try to extract timestamp and sender info
                        timestamp = None
                        is_from_me = False
                        sender = None
                        
                        # Try to find timestamp (WhatsApp stores precise timestamps in data attributes)
                        try:
                            # First, try to get the precise timestamp from data attributes
                            # WhatsApp stores timestamp in data-pre-plain-text or in span title attribute
                            timestamp_attr = elem.get_attribute("data-pre-plain-text")
                            if not timestamp_attr:
                                # Try to find span with title that contains timestamp
                                time_spans = elem.find_elements(By.CSS_SELECTOR, "span[title]")
                                for span in time_spans:
                                    title = span.get_attribute("title")
                                    if title and ("oggi" in title.lower() or "today" in title.lower() or ":" in title):
                                        timestamp_attr = title
                                        break
                            
                            if timestamp_attr:
                                # Parse timestamp from attribute
                                # Format could be: "[14:30, 04/11/2024] Nome:" or "[Oggi, 14:30] Nome:" or just time
                                import re
                                from datetime import timedelta
                                
                                # Try to extract date from format like "04/11/2024"
                                date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', timestamp_attr)
                                if date_match:
                                    day, month, year = map(int, date_match.groups())
                                    # Extract time from format like "14:30"
                                    time_match = re.search(r'(\d{1,2}):(\d{1,2})', timestamp_attr)
                                    if time_match:
                                        hour, minute = map(int, time_match.groups())
                                        timestamp = datetime(year, month, day, hour, minute)
                                    else:
                                        timestamp = datetime(year, month, day)
                                else:
                                    # Check for relative dates
                                    attr_lower = timestamp_attr.lower()
                                    if "oggi" in attr_lower or "today" in attr_lower:
                                        # Extract time if present
                                        time_match = re.search(r'(\d{1,2}):(\d{1,2})', timestamp_attr)
                                        if time_match:
                                            hour, minute = map(int, time_match.groups())
                                            timestamp = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                                        else:
                                            timestamp = datetime.now()
                                    elif "ieri" in attr_lower or "yesterday" in attr_lower:
                                        time_match = re.search(r'(\d{1,2}):(\d{1,2})', timestamp_attr)
                                        if time_match:
                                            hour, minute = map(int, time_match.groups())
                                            timestamp = (datetime.now() - timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                                        else:
                                            timestamp = datetime.now() - timedelta(days=1)
                                    else:
                                        # Just time, assume today
                                        time_match = re.search(r'(\d{1,2}):(\d{1,2})', timestamp_attr)
                                        if time_match:
                                            hour, minute = map(int, time_match.groups())
                                            timestamp = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                            
                            # Fallback: try to find time element in the message
                            if not timestamp:
                                time_selectors = [
                                    "[data-testid='msg-time']",
                                    "span[data-testid*='time']",
                                    ".message-time",
                                ]
                                for time_selector in time_selectors:
                                    try:
                                        time_elem = elem.find_element(By.CSS_SELECTOR, time_selector)
                                        time_text = time_elem.text.strip() or time_elem.get_attribute("title") or ""
                                        if time_text and ":" in time_text:
                                            # Try to parse time like "14:30"
                                            try:
                                                time_match = re.search(r'(\d{1,2}):(\d{1,2})', time_text)
                                                if time_match:
                                                    hour, minute = map(int, time_match.groups())
                                                    # Assume today if no date info
                                                    timestamp = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                                                    break
                                            except:
                                                pass
                                    except:
                                        continue
                        except Exception as e:
                            logger.debug(f"Error extracting timestamp: {e}")
                        
                        # Check if message is from me (sent) or received
                        try:
                            # Look for indicators of sent messages
                            sent_indicators = elem.find_elements(By.CSS_SELECTOR, "[data-testid*='sent'], [data-icon='msg-dblcheck'], [data-icon='msg-check']")
                            is_from_me = len(sent_indicators) > 0
                        except:
                            pass
                        
                        # Try to get sender name from contact name or chat title
                        if not is_from_me:
                            try:
                                # Look for sender name in message element
                                sender_elem = elem.find_element(By.CSS_SELECTOR, "[data-testid*='sender'], .message-sender")
                                sender = sender_elem.text.strip()
                            except:
                                pass
                        
                        message_data = {
                            "text": text,
                            "timestamp": timestamp.isoformat() if timestamp else None,
                            "date": timestamp.date().isoformat() if timestamp else None,
                            "is_from_me": is_from_me,
                            "sender": sender or ("Tu" if is_from_me else "Contatto"),
                        }
                        
                        messages.append(message_data)
                    except Exception as e:
                        logger.debug(f"Error extracting message: {e}")
                        continue
                
                # Filter by date if needed (keep all if no date filter)
                # Sort by timestamp (newest first) and limit to max_results
                messages_with_timestamp = [m for m in messages if m.get("timestamp")]
                messages_without_timestamp = [m for m in messages if not m.get("timestamp")]
                
                # Sort by timestamp descending
                messages_with_timestamp.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                
                # Combine: first timestamped, then untimestamped
                messages = messages_with_timestamp[:max_results] + messages_without_timestamp[:max_results-len(messages_with_timestamp)]
                
                logger.info(f"Successfully extracted {len(messages)} messages")
                        
            except TimeoutException:
                logger.warning("No messages found or timeout waiting for messages")
                # Try to get page source for debugging
                try:
                    page_source_snippet = self.driver.page_source[:500]
                    logger.debug(f"Page source snippet: {page_source_snippet}")
                except:
                    pass
                return []
                
        except Exception as e:
            logger.error(f"Error getting messages: {e}", exc_info=True)
            raise Exception(f"Error retrieving messages: {str(e)}")
        
        return messages
    
    async def send_message_pywhatkit(
        self,
        phone_number: str,
        message: str,
        hour: int = None,
        minute: int = None,
    ):
        """Send WhatsApp message using pywhatkit (requires WhatsApp Web already open)"""
        if hour is None or minute is None:
            now = time.localtime()
            hour = now.tm_hour
            minute = now.tm_min + 1  # Send in 1 minute
        
        # Remove + and spaces from phone number
        phone_number = phone_number.replace("+", "").replace(" ", "")
        
        pwt.sendwhatmsg(f"+{phone_number}", message, hour, minute)
    
    async def close(self):
        """Close WhatsApp Web session"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WhatsApp Web session closed")
            except Exception as e:
                logger.error(f"Error closing WhatsApp session: {e}")
            finally:
                self.driver = None
                self.is_authenticated = False

