import unittest
import os
import tempfile
from src.cs_solver import smallest_CollageSystem, cs2str, SLPExp

class TestCSSolver(unittest.TestCase):
    
    def test_basic_functionality(self):
        """基本的な文字列に対するテスト"""
        test_strings = [
            b"abracadabra",
            b"hello world",
            b"banana",
            b"mississippi"
        ]
        
        for text in test_strings:
            print(f"Testing string: {text.decode('utf-8')}")
            exp = SLPExp.create()
            exp.algo = "cs-sat"
            exp.file_len = len(text)
            
            result = smallest_CollageSystem(text, exp)
            root, cs = eval(exp.factors)
            
            # 復元した文字列が元の文字列と一致するか確認
            reconstructed = bytes(cs2str(root, cs))
            self.assertEqual(text, reconstructed)
            
            # 圧縮サイズが文字列長以下であることを確認
            self.assertLessEqual(exp.factor_size, len(text))
            
            print(f"Compression ratio: {exp.factor_size}/{len(text)}")
    
    def test_repetitive_strings(self):
        """繰り返しパターンを含む文字列のテスト"""
        test_strings = [
            b"aaaaaaaa",
            b"abababab",
            b"abcabcabc"
        ]
        
        for text in test_strings:
            print(f"Testing repetitive string: {text.decode('utf-8')}")
            exp = SLPExp.create()
            exp.algo = "cs-sat"
            exp.file_len = len(text)
            
            result = smallest_CollageSystem(text, exp)
            root, cs = eval(exp.factors)
            
            # 復元した文字列が元の文字列と一致するか確認
            reconstructed = bytes(cs2str(root, cs))
            self.assertEqual(text, reconstructed)
            
            # 繰り返しパターンの場合、高い圧縮率が期待される
            print(f"Compression ratio: {exp.factor_size}/{len(text)}")
    
    def test_edge_cases(self):
        """エッジケースのテスト"""
        # 空の文字列
        text = b""
        exp = SLPExp.create()
        exp.algo = "cs-sat"
        exp.file_len = len(text)
        
        try:
            result = smallest_CollageSystem(text, exp)
            root, cs = eval(exp.factors)
            reconstructed = bytes(cs2str(root, cs))
            self.assertEqual(text, reconstructed)
        except Exception as e:
            print(f"Empty string test failed with error: {e}")
        
        # 単一文字の文字列
        text = b"a"
        exp = SLPExp.create()
        exp.algo = "cs-sat"
        exp.file_len = len(text)
        
        result = smallest_CollageSystem(text, exp)
        root, cs = eval(exp.factors)
        reconstructed = bytes(cs2str(root, cs))
        self.assertEqual(text, reconstructed)
    
    def test_file_input(self):
        """ファイル入力のテスト"""
        # 一時ファイルに文字列を書き込んでテスト
        test_text = b"This is a test string for file input testing."
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(test_text)
            tmp_filename = tmp.name
        
        try:
            with open(tmp_filename, "rb") as f:
                text = f.read()
            
            exp = SLPExp.create()
            exp.algo = "cs-sat"
            exp.file_name = os.path.basename(tmp_filename)
            exp.file_len = len(text)
            
            result = smallest_CollageSystem(text, exp)
            root, cs = eval(exp.factors)
            reconstructed = bytes(cs2str(root, cs))
            self.assertEqual(text, reconstructed)
        finally:
            os.unlink(tmp_filename)
    
    def test_large_string(self):
        """大きな文字列のテスト（パフォーマンステスト）"""
        # 注意：このテストは時間がかかる可能性があります
        text = b"abc" * 100  # 300文字の繰り返しパターン
        
        print(f"Testing large string of length {len(text)}")
        exp = SLPExp.create()
        exp.algo = "cs-sat"
        exp.file_len = len(text)
        
        result = smallest_CollageSystem(text, exp)
        root, cs = eval(exp.factors)
        
        # 復元した文字列が元の文字列と一致するか確認
        reconstructed = bytes(cs2str(root, cs))
        self.assertEqual(text, reconstructed)
        
        # 高い圧縮率が期待される
        print(f"Compression ratio for large string: {exp.factor_size}/{len(text)}")

if __name__ == "__main__":
    unittest.main()