# Comprehensive Mortgage Document Analysis Setup

## Overview
The mortgage document analysis feature provides **professional-grade legal analysis** of mortgage agreements from the perspective of an experienced real-estate attorney and consumer-rights advocate. Users can upload their mortgage documents (PDF, PNG, JPG) and receive a comprehensive 9-section analysis covering all critical aspects of their mortgage terms.

## Analysis Format
The system provides analysis in the following structured format:

1. **Executive Summary** - Concise overview of loan purpose, parties, and key risks/benefits
2. **Key Financial Terms** - Interest rates, APR, payment frequency, insurance requirements  
3. **Fees & Penalties** - Late fees, prepayment penalties, balloon payments, "junk" fees
4. **Borrower Obligations & Covenants** - Escrow, insurance, maintenance, occupancy requirements
5. **Lender Rights & Remedies** - Default definitions, foreclosure procedures, dispute resolution
6. **Risk / Red-Flag Checklist** - Unusual, costly, or ambiguous terms requiring attention
7. **Comparison to Market Norms** - Rate and fee comparisons to regional averages (when available)
8. **Questions for the Borrower** - Specific clarifications to request before signing
9. **References** - Clause and page number citations for verification

## Prerequisites

### 1. Install Tesseract OCR
For image text extraction, you need to install Tesseract OCR:

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Install Python Dependencies
```bash
cd personal-finance-app
source venv/bin/activate  # Activate your virtual environment
pip install -r requirements.txt
```

### 3. OpenAI API Integration (Recommended for Full Analysis)
For the complete legal analysis experience, set up OpenAI API:

1. Get an API key from https://platform.openai.com/
2. Set environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
3. The system automatically detects the API key and uses GPT-4 for comprehensive analysis

**Note:** Without OpenAI API, the system provides rule-based analysis with pattern matching.

## Usage

1. **Start the Flask Application:**
   ```bash
   cd personal-finance-app
   source venv/bin/activate
   python app.py
   ```

2. **Access the Applications:**
   - Mortgage Rate Comparison + Analysis: http://localhost:5000/
   - Plaid Demo with Mortgage Analysis: http://localhost:5000/plaid-demo

3. **Upload Mortgage Document:**
   - Navigate to the mortgage analysis section
   - Click "Choose File" or drag-and-drop your mortgage document
   - Supported formats: PDF, PNG, JPG (max 16MB)
   - Click "🔍 Analyze Document"
   - Wait for the comprehensive analysis results

## Analysis Capabilities

### With OpenAI API (GPT-4) - Full Legal Analysis:
- ✅ **Professional legal perspective** - Analysis from experienced attorney viewpoint
- ✅ **Plain-English explanations** - Complex terms explained for non-lawyers
- ✅ **Comprehensive risk assessment** - Identifies unusual or problematic terms
- ✅ **Market comparisons** - Rates and fees compared to regional standards
- ✅ **Specific recommendations** - Actionable questions to ask lenders
- ✅ **Document references** - Specific clause and page citations
- ✅ **Consumer protection focus** - Emphasis on borrower rights and potential issues

### Without OpenAI API - Rule-Based Analysis:
- ✅ Text extraction from PDF documents  
- ✅ OCR text extraction from images
- ✅ Basic mortgage term identification
- ✅ Interest rate and payment detection
- ✅ Fee and penalty identification
- ✅ Insurance and escrow requirements

## Tips for Best Results

### Document Quality:
- **High resolution images** - Clear, well-lit scans work best for OCR
- **Complete documents** - Upload full mortgage agreement, not just excerpts
- **Readable text** - Ensure all text is clearly visible and not cut off

### OpenAI API Usage:
- **Set API key** - Provides dramatically better analysis quality
- **Complete text extraction** - Ensure documents are fully readable
- **Review all sections** - Pay special attention to Risk/Red-Flag section

## Supported File Types
- **PDF**: `.pdf` (preferred for text-based documents)
- **Images**: `.png`, `.jpg`, `.jpeg` (for scanned documents)
- **Max file size**: 16MB

## Security & Privacy
- Documents are processed temporarily and **immediately deleted** after analysis
- No document content is permanently stored on the server
- For production use, implement additional security measures as needed
- OpenAI API calls are subject to OpenAI's privacy policy

## Troubleshooting

### Common Issues:

1. **"Tesseract not found" error:**
   - Ensure Tesseract is installed and in your system PATH
   - On Windows, you might need to specify the tesseract path

2. **Poor OCR results:**
   - Use high-resolution, well-lit document scans
   - Ensure good contrast between text and background
   - Consider converting PDF to image if text extraction fails

3. **Limited analysis without OpenAI:**
   - Set up OpenAI API key for comprehensive legal analysis
   - Rule-based analysis provides basic term identification only

4. **Analysis doesn't match document sections:**
   - Verify document text was extracted correctly
   - Check for incomplete or corrupted uploads
   - Try different file formats (PDF vs image)

## Professional Disclaimer
This tool provides **educational analysis** to help borrowers understand their mortgage documents. It is **not a substitute for professional legal advice**. Always consult with a qualified attorney for specific legal questions or concerns about your mortgage agreement.

## Next Steps for Enhanced Analysis
- Configure OpenAI API key for full legal analysis capabilities
- Consider document preprocessing for optimal text extraction
- Implement user authentication for analysis history (optional)
- Add support for additional document types as needed 