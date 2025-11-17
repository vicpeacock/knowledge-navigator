#!/usr/bin/env python3
"""
Unit tests per i test cases di evaluation
Verifica che tutti i test cases siano correttamente definiti
"""
import pytest
from tests.evaluation.test_cases import (
    ALL_TEST_CASES,
    CALENDAR_TEST_CASES,
    EMAIL_TEST_CASES,
    WEB_SEARCH_TEST_CASES,
    MAPS_TEST_CASES,
    MEMORY_TEST_CASES,
    GENERAL_TEST_CASES,
    get_test_cases_by_category,
    get_test_cases_by_id,
)
from app.core.evaluation import TestCase


class TestTestCasesLoading:
    """Test per caricamento test cases"""
    
    def test_all_test_cases_loaded(self):
        """Verifica che tutti i test cases siano caricati"""
        assert len(ALL_TEST_CASES) > 0
        assert all(isinstance(tc, TestCase) for tc in ALL_TEST_CASES)
    
    def test_test_cases_have_unique_ids(self):
        """Verifica che tutti i test cases abbiano ID unici"""
        ids = [tc.id for tc in ALL_TEST_CASES]
        assert len(ids) == len(set(ids)), "Test cases devono avere ID unici"
    
    def test_test_cases_have_required_fields(self):
        """Verifica che tutti i test cases abbiano i campi richiesti"""
        for tc in ALL_TEST_CASES:
            assert tc.id, f"Test case {tc.name} deve avere un ID"
            assert tc.name, f"Test case {tc.id} deve avere un nome"
            assert tc.description, f"Test case {tc.id} deve avere una descrizione"
            assert tc.input_message, f"Test case {tc.id} deve avere un input message"
            assert tc.category, f"Test case {tc.id} deve avere una categoria"
            assert tc.min_response_length > 0, f"Test case {tc.id} deve avere min_response_length > 0"
            assert tc.max_latency_seconds > 0, f"Test case {tc.id} deve avere max_latency_seconds > 0"


class TestTestCasesByCategory:
    """Test per filtri per categoria"""
    
    def test_calendar_test_cases(self):
        """Verifica test cases calendario"""
        assert len(CALENDAR_TEST_CASES) == 3
        for tc in CALENDAR_TEST_CASES:
            assert tc.category == "calendar"
            # Le descrizioni possono essere in inglese o italiano
            desc_lower = tc.description.lower()
            assert ("calendar" in desc_lower or "event" in desc_lower or 
                    "calendario" in desc_lower or "evento" in desc_lower)
    
    def test_email_test_cases(self):
        """Verifica test cases email"""
        assert len(EMAIL_TEST_CASES) == 3
        for tc in EMAIL_TEST_CASES:
            assert tc.category == "email"
            assert "email" in tc.description.lower()
    
    def test_web_search_test_cases(self):
        """Verifica test cases web search"""
        assert len(WEB_SEARCH_TEST_CASES) == 2
        for tc in WEB_SEARCH_TEST_CASES:
            assert tc.category == "web_search"
    
    def test_maps_test_cases(self):
        """Verifica test cases maps"""
        assert len(MAPS_TEST_CASES) == 2
        for tc in MAPS_TEST_CASES:
            assert tc.category == "maps"
    
    def test_memory_test_cases(self):
        """Verifica test cases memory"""
        assert len(MEMORY_TEST_CASES) == 2
        for tc in MEMORY_TEST_CASES:
            assert tc.category == "memory"
    
    def test_general_test_cases(self):
        """Verifica test cases general"""
        assert len(GENERAL_TEST_CASES) == 2
        for tc in GENERAL_TEST_CASES:
            assert tc.category == "general"
    
    def test_get_test_cases_by_category(self):
        """Test funzione get_test_cases_by_category"""
        calendar_tests = get_test_cases_by_category("calendar")
        assert len(calendar_tests) == 3
        assert all(tc.category == "calendar" for tc in calendar_tests)
        
        email_tests = get_test_cases_by_category("email")
        assert len(email_tests) == 3
        assert all(tc.category == "email" for tc in email_tests)
        
        # Test categoria inesistente
        unknown_tests = get_test_cases_by_category("unknown")
        assert len(unknown_tests) == 0


class TestTestCasesByID:
    """Test per filtri per ID"""
    
    def test_get_test_cases_by_id(self):
        """Test funzione get_test_cases_by_id"""
        # Test con ID esistenti
        test_ids = ["calendar_001", "email_001", "web_001"]
        results = get_test_cases_by_id(test_ids)
        assert len(results) == 3
        assert all(tc.id in test_ids for tc in results)
        
        # Test con ID inesistente
        results = get_test_cases_by_id(["nonexistent_001"])
        assert len(results) == 0
        
        # Test con mix di ID esistenti e inesistenti
        results = get_test_cases_by_id(["calendar_001", "nonexistent_001"])
        assert len(results) == 1
        assert results[0].id == "calendar_001"


class TestTestCasesContent:
    """Test per contenuto dei test cases"""
    
    def test_calendar_test_cases_have_expected_tools(self):
        """Verifica che i test cases calendario abbiano tool attesi"""
        for tc in CALENDAR_TEST_CASES:
            assert tc.expected_tools is not None
            assert len(tc.expected_tools) > 0
            # Verifica che i tool siano relativi al calendario
            assert any("calendar" in tool.lower() for tool in tc.expected_tools)
    
    def test_email_test_cases_have_expected_tools(self):
        """Verifica che i test cases email abbiano tool attesi"""
        for tc in EMAIL_TEST_CASES:
            assert tc.expected_tools is not None
            assert len(tc.expected_tools) > 0
            # Verifica che i tool siano relativi alle email
            assert any("email" in tool.lower() for tool in tc.expected_tools)
    
    def test_web_search_test_cases_have_expected_tools(self):
        """Verifica che i test cases web search abbiano tool attesi"""
        for tc in WEB_SEARCH_TEST_CASES:
            assert tc.expected_tools is not None
            assert len(tc.expected_tools) > 0
            # Verifica che i tool siano relativi alla ricerca web
            assert any("web" in tool.lower() or "search" in tool.lower() for tool in tc.expected_tools)
    
    def test_maps_test_cases_have_expected_tools(self):
        """Verifica che i test cases maps abbiano tool attesi"""
        for tc in MAPS_TEST_CASES:
            assert tc.expected_tools is not None
            assert len(tc.expected_tools) > 0
            # Verifica che i tool siano relativi a Google Maps
            assert any("maps" in tool.lower() or "map" in tool.lower() for tool in tc.expected_tools)
    
    def test_test_cases_have_expected_keywords(self):
        """Verifica che i test cases abbiano keywords attese"""
        for tc in ALL_TEST_CASES:
            # Non tutti i test cases devono avere keywords, ma se le hanno devono essere valide
            if tc.expected_keywords:
                assert len(tc.expected_keywords) > 0
                assert all(isinstance(kw, str) and len(kw) > 0 for kw in tc.expected_keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

