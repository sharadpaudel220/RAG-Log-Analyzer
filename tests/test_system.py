import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.input_layer.log_ingestion import LogIngestion, RawLogEntry
from src.preprocessing.log_preprocessor import LogPreprocessor
from src.knowledge_base.knowledge_manager import KnowledgeBaseManager

class TestLogIngestion(unittest.TestCase):
    def setUp(self):
        self.ingestion = LogIngestion()
    
    def test_raw_log_entry_creation(self):
        entry = RawLogEntry(
            content="Test log message",
            source_file="test.log",
            line_number=1
        )
        self.assertEqual(entry.content, "Test log message")
        self.assertEqual(entry.line_number, 1)
    
    def test_timestamp_extraction(self):
        log_line = "2024-01-15 10:23:45 INFO Test message"
        timestamp = self.ingestion._extract_timestamp(log_line)
        self.assertIsNotNone(timestamp)

class TestLogPreprocessor(unittest.TestCase):
    def setUp(self):
        self.preprocessor = LogPreprocessor()
    
    def test_severity_extraction(self):
        content = "ERROR: Something went wrong"
        severity = self.preprocessor._extract_severity(content)
        self.assertEqual(severity, "ERROR")
    
    def test_component_extraction(self):
        content = "[DataNode] Processing block"
        component = self.preprocessor._extract_component(content)
        self.assertEqual(component, "DataNode")

class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.kb_manager = KnowledgeBaseManager(storage_path="data/test_kb")
    
    def test_add_document(self):
        doc = self.kb_manager.add_document(
            content="Test document content",
            title="Test Document",
            doc_type="test"
        )
        self.assertIsNotNone(doc)
        self.assertEqual(doc.title, "Test Document (Part 1)")
    
    def test_build_index(self):
        self.kb_manager.add_document(
            content="Test content",
            title="Test",
            doc_type="test"
        )
        self.kb_manager.build_index()
        self.assertIsNotNone(self.kb_manager.index)
        self.assertGreater(self.kb_manager.index.ntotal, 0)

if __name__ == '__main__':
    unittest.main()
