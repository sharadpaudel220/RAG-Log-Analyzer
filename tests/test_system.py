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

    def test_case1_drain3_parsing_hdfs_log(self):
        """Case 1 - Log Preprocessing: Drain3 Parsing

        Objective: Verify that the Drain3 log preprocessing module correctly
        parses a raw HDFS log entry and produces a structured output dictionary
        containing all required fields, addressing Objective O3.

        Action: Pass the raw HDFS log entry to the LogPreprocessor class.
        Inspect the returned dictionary for template_id, template_text,
        severity, component, timestamp, and variables fields.

        Expected Result: template_id is valid (>0), severity=INFO,
        component=None (HDFS dotted-class format not matched by bracket/colon
        pattern), template_text is a non-empty string with variable tokens
        masked by Drain3. No exceptions are raised.
        """
        raw_log = (
            "081109 203518 143 INFO dfs.DataNode$DataXceiver: "
            "Receiving block blk_-1608999687919862906  src: "
            "/10.251.31.5:54106 dest: /10.251.31.5:50010"
        )
        raw_entry = RawLogEntry(content=raw_log, source_file="HDFS.log", line_number=1)

        results = self.preprocessor.preprocess([raw_entry])

        self.assertEqual(len(results), 1, "Should return exactly one parsed entry")
        parsed = results[0]
        result_dict = parsed.to_dict()

        # All required fields must be present in the output dictionary
        for field_name in ['template_id', 'template', 'severity', 'component', 'raw_content']:
            self.assertIn(field_name, result_dict, f"Missing required field: {field_name}")

        # template_id must be a valid positive integer assigned by Drain3
        self.assertIsInstance(result_dict['template_id'], int)
        self.assertGreater(result_dict['template_id'], 0,
                           "template_id should be a valid positive cluster ID")

        # severity should be INFO (log line contains the token 'INFO')
        self.assertEqual(result_dict['severity'], 'INFO',
                         f"Expected severity INFO, got {result_dict['severity']}")

        # component: the system regex matches [..], (..), or ^word: patterns.
        # 'dfs.DataNode$DataXceiver:' is a dotted-class token that does not match
        # those patterns, so component is correctly None per current implementation.
        self.assertIsNone(result_dict['component'],
                          f"component expected None for dotted-class HDFS format, "
                          f"got {result_dict['component']}")

        # raw_content must preserve the original log entry unchanged
        self.assertEqual(result_dict['raw_content'], raw_log)

        # template must be a non-empty string returned by Drain3
        self.assertIsInstance(result_dict['template'], str)
        self.assertTrue(len(result_dict['template']) > 0,
                        "template_text should not be empty")

        print("\n--- Case 1: Drain3 Parsing Test ---")
        print(f"  raw_content  : {result_dict['raw_content'][:80]}...")
        print(f"  template_id  : {result_dict['template_id']}")
        print(f"  template_text: {result_dict['template']}")
        print(f"  severity     : {result_dict['severity']}")
        print(f"  component    : {result_dict['component']}")
        print(f"  timestamp    : {result_dict['timestamp']}")
        print(f"  parameters   : {result_dict['parameters']}")
        print("  RESULT       : Test PASSED")

    def test_case2_severity_extraction(self):
        """Case 2 - Log Preprocessing: Severity Extraction

        Objective: Verify that the severity extraction logic correctly identifies
        severity levels from raw log text for both HDFS and BGL log formats,
        addressing Objective O3.

        Action: Pass five log entries containing the keywords CRITICAL, ERROR,
        WARNING, INFO, and DEBUG respectively to the LogPreprocessor. Extract
        the severity field from each returned dictionary. Verify each severity
        matches the keyword present in the log.

        Expected Result: Each log entry returns a severity field exactly matching
        its keyword. Logs with no severity keyword default to INFO.
        """
        test_cases = [
            ("CRITICAL: kernel panic detected on node BGL/R00-M0-N00",   "CRITICAL"),
            ("ERROR: failed to write block blk_-1608999687919862906",     "ERROR"),
            ("WARNING: disk usage above 90% on DataNode /10.251.31.5",    "WARNING"),
            ("081109 203518 143 INFO dfs.DataNode: heartbeat received",    "INFO"),
            ("DEBUG: connection pool size=10 active=3",                    "DEBUG"),
            ("081109 203518 143 dfs.DataNode: no level keyword here",      "INFO"),  # default
        ]

        print("\n--- Case 2: Severity Extraction Test ---")
        for raw_log, expected_severity in test_cases:
            raw_entry = RawLogEntry(content=raw_log, source_file="test.log", line_number=1)
            results = self.preprocessor.preprocess([raw_entry])
            result_dict = results[0].to_dict()
            actual = result_dict['severity']

            print(f"  log      : {raw_log[:70]}")
            print(f"  expected : {expected_severity}  |  actual: {actual}")

            self.assertEqual(actual, expected_severity,
                             f"Expected severity '{expected_severity}' for log: {raw_log}")

        print("  RESULT   : Test PASSED - all 5 severity levels + default correctly extracted")

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
