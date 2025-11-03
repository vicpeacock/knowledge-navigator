from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pywhatkit as pwt


class WhatsAppService:
    """Service for WhatsApp integration using Python libraries"""
    
    def __init__(self):
        self.driver = None
        self.is_authenticated = False
    
    async def setup_whatsapp_web(
        self,
        headless: bool = False,
        profile_path: Optional[str] = None,
    ):
        """Setup WhatsApp Web using Selenium"""
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        
        if profile_path:
            options.add_argument(f"--user-data-dir={profile_path}")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get("https://web.whatsapp.com")
        
        # Wait for QR code scan or existing session
        # User needs to scan QR code manually
        WebDriverWait(self.driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']"))
        )
        
        self.is_authenticated = True
    
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
            self.driver.quit()
            self.is_authenticated = False

