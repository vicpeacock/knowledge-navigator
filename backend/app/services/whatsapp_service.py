from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time
import pywhatkit as pwt
import platform
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp integration using Python libraries"""
    
    def __init__(self):
        self.driver = None
        self.is_authenticated = False
    
    def _get_chrome_options(self, headless: bool = False, profile_path: Optional[str] = None):
        """Get Chrome options with proper configuration for macOS/Linux"""
        options = webdriver.ChromeOptions()
        
        # Basic options
        if headless:
            options.add_argument("--headless")
            options.add_argument("--headless=new")  # Use new headless mode
        
        # User data directory
        if profile_path:
            options.add_argument(f"--user-data-dir={profile_path}")
        
        # Security and stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        
        # macOS specific options
        if platform.system() == "Darwin":  # macOS
            options.add_argument("--disable-features=VizDisplayCompositor")
            # Allow Chrome to run without explicit ChromeDriver path
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
        
        # Windows/Linux options
        if platform.system() == "Windows":
            options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Additional stability
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        
        # Prefs for better WhatsApp Web compatibility
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1,
        }
        options.add_experimental_option("prefs", prefs)
        
        return options
    
    async def setup_whatsapp_web(
        self,
        headless: bool = False,
        profile_path: Optional[str] = None,
    ):
        """Setup WhatsApp Web using Selenium"""
        try:
            options = self._get_chrome_options(headless=headless, profile_path=profile_path)
            
            # Try to create Chrome driver using webdriver-manager for automatic ChromeDriver management
            try:
                # Use webdriver-manager to automatically download and manage ChromeDriver
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                logger.error(f"Failed to initialize Chrome driver with webdriver-manager: {e}")
                # Fallback: try without service (ChromeDriver in PATH)
                try:
                    logger.info("Trying fallback: ChromeDriver from PATH")
                    self.driver = webdriver.Chrome(options=options)
                except WebDriverException as e2:
                    logger.error(f"Failed to initialize Chrome driver: {e2}")
                    raise Exception(
                        f"ChromeDriver initialization failed. "
                        f"Please ensure Chrome browser is installed. "
                        f"webdriver-manager will download ChromeDriver automatically. "
                        f"Error: {str(e2)}"
                    )
            
            logger.info("Chrome driver initialized successfully")
            
            # Navigate to WhatsApp Web
            self.driver.get("https://web.whatsapp.com")
            logger.info("Navigated to WhatsApp Web")
            
            # Wait for QR code scan or existing session
            # User needs to scan QR code manually
            try:
                WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']"))
                )
                logger.info("WhatsApp Web authenticated successfully")
                self.is_authenticated = True
            except TimeoutException:
                # Check if QR code is still visible (not authenticated yet)
                try:
                    qr_code = self.driver.find_element(By.CSS_SELECTOR, "[data-ref]")
                    if qr_code:
                        logger.warning("QR code still visible - user needs to scan")
                        self.is_authenticated = False
                        raise Exception(
                            "WhatsApp Web QR code detected. Please scan the QR code with your phone. "
                            "The session will be authenticated once you scan it."
                        )
                except:
                    # If we can't find QR code, assume we're authenticated or there's an error
                    logger.warning("Could not determine authentication status")
                    # Set as authenticated anyway - user can try to use it
                    self.is_authenticated = True
                    
        except Exception as e:
            logger.error(f"Error setting up WhatsApp Web: {e}")
            # Clean up driver if it was created
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            raise Exception(f"Error setting up WhatsApp: {str(e)}")
    
    async def get_recent_messages(
        self,
        contact_name: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent WhatsApp messages"""
        if not self.is_authenticated or not self.driver:
            raise ValueError("WhatsApp Web not authenticated")
        
        messages = []
        
        if contact_name:
            # Search for contact
            search_box = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='chat-search-input']")
            search_box.send_keys(contact_name)
            time.sleep(2)
            
            # Click on first result
            first_result = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='chat-item']")
            first_result.click()
            time.sleep(2)
        
        # Get messages from active chat
        message_elements = self.driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='message-container']"
        )
        
        for elem in message_elements[-max_results:]:
            try:
                text_elem = elem.find_element(By.CSS_SELECTOR, "[data-testid='message-text']")
                text = text_elem.text
                messages.append({"text": text})
            except Exception:
                pass
        
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

