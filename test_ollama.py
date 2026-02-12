#!/usr/bin/env python3
"""
Test script to verify Ollama connection and Mistral model
"""

import requests
import json

def test_ollama_connection():
    print("="*80)
    print("Testing Ollama Connection")
    print("="*80)
    print()
    
    base_url = "http://localhost:11434"
    
    # Test 1: Check if Ollama is running
    print("1. Checking if Ollama service is running...")
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print("   ✓ Ollama service is running")
            models = response.json().get('models', [])
            print(f"   ✓ Found {len(models)} model(s)")
            for model in models:
                print(f"      - {model['name']}")
        else:
            print(f"   ✗ Unexpected response: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to Ollama. Is it running?")
        print("   Run: ollama serve")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    print()
    
    # Test 2: Check if Mistral model is available
    print("2. Checking if mistral:7b-instruct model is available...")
    mistral_available = any('mistral' in m['name'] for m in models)
    if mistral_available:
        print("   ✓ Mistral model is available")
    else:
        print("   ✗ Mistral model not found")
        print("   Run: ollama pull mistral:7b-instruct")
        return False
    
    print()
    
    # Test 3: Test generation
    print("3. Testing text generation with Mistral...")
    try:
        payload = {
            "model": "mistral:7b-instruct",
            "prompt": "Analyze this log: ERROR: Connection timeout. Provide a brief diagnosis.",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 100
            }
        }
        
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            generated_text = result.get('response', '')
            print("   ✓ Generation successful!")
            print(f"   Response preview: {generated_text[:150]}...")
            print(f"   Tokens: {result.get('eval_count', 0)}")
            print(f"   Time: {result.get('total_duration', 0) / 1e9:.2f}s")
        else:
            print(f"   ✗ Generation failed: {response.status_code}")
            print(f"   {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ Error during generation: {e}")
        return False
    
    print()
    print("="*80)
    print("✓ All tests passed! Ollama is ready to use.")
    print("="*80)
    return True

if __name__ == "__main__":
    success = test_ollama_connection()
    exit(0 if success else 1)
