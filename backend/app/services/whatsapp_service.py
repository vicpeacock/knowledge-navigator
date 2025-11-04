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
        # Default profile path for persistent sessions
        self.default_profile_path = Path.home() / ".whatsapp_web_profile"
    
    def _get_chrome_options(self, headless: bool = False, profile_path: Optional[str] = None):
        """Get Chrome options with proper configuration for macOS/Linux"""
        options = webdriver.ChromeOptions()
        
        # Use persistent profile by default to save session
        final_profile_path = profile_path or str(self.default_profile_path)
        if not headless:  # Only use persistent profile if not headless
            # Ensure profile directory exists
            Path(final_profile_path).mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={final_profile_path}")
            logger.info(f"Using persistent profile: {final_profile_path}")
        
        # Basic options
        if headless:
            options.add_argument("--headless=new")  # Use new headless mode
        else:
            # Non-headless: show window for QR code scanning
            options.add_argument("--window-size=1280,800")
            options.add_argument("--start-maximized")
        
        # Security and stability options (essential for macOS)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        
        # macOS specific options
        if platform.system() == "Darwin":  # macOS
            options.add_argument("--disable-features=VizDisplayCompositor")
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
            return {"authenticated": False, "status": "no_driver"}
        
        try:
            # Check for chat list (authenticated)
            try:
                chat_list = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='chat-list']")
                if chat_list:
                    return {"authenticated": True, "status": "authenticated"}
            except NoSuchElementException:
                pass
            
            # Check for QR code (not authenticated)
            try:
                qr_code = self.driver.find_element(By.CSS_SELECTOR, "[data-ref]")
                if qr_code:
                    return {"authenticated": False, "status": "qr_code_visible", "message": "Please scan QR code"}
            except NoSuchElementException:
                pass
            
            # Check for loading screen
            try:
                loading = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='loading']")
                if loading:
                    return {"authenticated": False, "status": "loading", "message": "WhatsApp Web is loading"}
            except NoSuchElementException:
                pass
            
            # Unknown state
            return {"authenticated": False, "status": "unknown", "message": "Could not determine authentication status"}
            
        except Exception as e:
            logger.error(f"Error checking authentication status: {e}")
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
            
            options = self._get_chrome_options(headless=headless, profile_path=profile_path)
            
            # Try to create Chrome driver using webdriver-manager for automatic ChromeDriver management
            # Use thread executor to avoid blocking event loop
            import asyncio
            import concurrent.futures
            
            try:
                logger.info("Initializing Chrome driver with webdriver-manager...")
                
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
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("ChromeDriver initialization timed out")
                        raise Exception("ChromeDriver initialization timed out after 10 seconds")
                    except Exception as e:
                        logger.warning(f"Failed with webdriver-manager: {e}")
                        # Fallback: try without service
                        try:
                            logger.info("Trying fallback: ChromeDriver from PATH")
                            self.driver = await asyncio.wait_for(
                                loop.run_in_executor(executor, lambda: webdriver.Chrome(options=options)),
                                timeout=10.0
                            )
                        except Exception as e2:
                            logger.error(f"Fallback also failed: {e2}")
                            raise Exception(f"ChromeDriver failed: {str(e2)}")
                            
            except Exception as e:
                logger.error(f"ChromeDriver initialization error: {e}")
                raise Exception(f"ChromeDriver initialization failed: {str(e)}")
            
            logger.info("Chrome driver initialized successfully")
            
            # Navigate to WhatsApp Web
            logger.info("Navigating to WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            
            # Wait a bit for page to load
            time.sleep(3)
            
            # Check initial status
            status = self._check_authentication_status()
            logger.info(f"Initial authentication status: {status}")
            
            if status["authenticated"]:
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
                    "message": "WhatsApp Web opened. Please scan the QR code with your phone. Use /status endpoint to check authentication.",
                    "authenticated": False,
                    "status": "waiting_for_qr_scan",
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
            if contact_name:
                # Search for contact
                try:
                    search_box = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-search-input']"))
                    )
                    search_box.clear()
                    search_box.send_keys(contact_name)
                    time.sleep(2)
                    
                    # Click on first result
                    first_result = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='chat-item']"))
                    )
                    first_result.click()
                    time.sleep(2)
                except (TimeoutException, NoSuchElementException) as e:
                    logger.warning(f"Could not find contact '{contact_name}': {e}")
                    # Continue to get messages from current chat
            else:
                # Get messages from the first chat in the list (most recent)
                try:
                    first_chat = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='chat-item']"))
                    )
                    first_chat.click()
                    time.sleep(2)
                except (TimeoutException, NoSuchElementException) as e:
                    logger.warning(f"Could not open chat: {e}")
                    return []
            
            # Get messages from active chat
            try:
                message_elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='message-container']"))
                )
                
                for elem in message_elements[-max_results:]:
                    try:
                        # Try different selectors for message text
                        text = None
                        for selector in [
                            "[data-testid='message-text']",
                            "span.selectable-text",
                            ".message-text",
                        ]:
                            try:
                                text_elem = elem.find_element(By.CSS_SELECTOR, selector)
                                text = text_elem.text
                                break
                            except NoSuchElementException:
                                continue
                        
                        if text:
                            messages.append({"text": text})
                    except Exception as e:
                        logger.debug(f"Error extracting message: {e}")
                        continue
                        
            except TimeoutException:
                logger.warning("No messages found or timeout waiting for messages")
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

