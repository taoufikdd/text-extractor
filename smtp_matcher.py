<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>⚡ SMTP Extractor & Scan Matcher</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      background-color: #1e1e1e;
      color: #d4d4d4;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 20px;
    }
    h1 {
      font-size: 22px;
      margin-bottom: 20px;
      color: #ffffff;
    }
    .container {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 768px) {
      .container {
        grid-template-columns: 1fr;
      }
    }
    .box {
      display: flex;
      flex-direction: column;
      gap: 15px;
    }
    label {
      font-weight: bold;
      color: #61afef;
      font-size: 13px;
      display: block;
      margin-bottom: 6px;
    }
    textarea {
      width: 100%;
      height: 320px;
      background-color: #252526;
      color: #d4d4d4;
      font-family: 'Courier New', Courier, monospace;
      font-size: 13px;
      border: 1px solid #3c3c3c;
      border-radius: 4px;
      padding: 10px;
      resize: vertical;
      outline: none;
    }
    textarea:focus {
      border-color: #61afef;
    }
  </style>
</head>
<body>

  <h1>⚡ SMTP Extractor & Scan Matcher</h1>

  <div class="container">
    <!-- Left Column: Inputs -->
    <div class="box">
      <div>
        <label for="all_smtps">1. ALL_SMTPS (PASTE RAW SMTPS)</label>
        <textarea id="all_smtps" placeholder="Paste All_smtps list here..."></textarea>
      </div>
      <div>
        <label for="good_scan">3. GOOD_SCAN (PASTE SCANNED EMAILS/LIST)</label>
        <textarea id="good_scan" placeholder="Paste Good_scan emails here..."></textarea>
      </div>
    </div>

    <!-- Right Column: Outputs -->
    <div class="box">
      <div>
        <label id="lbl_extract">2. EXTRACT_EMAIL (EXTRACTED: 0)</label>
        <textarea id="extract_email" readonly></textarea>
      </div>
      <div>
        <label id="lbl_matched">4. TEST_ALL (MATCHED: 0)</label>
        <textarea id="test_all" readonly></textarea>
      </div>
    </div>
  </div>

  <script>
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;

    const inputSmtps = document.getElementById('all_smtps');
    const inputScan = document.getElementById('good_scan');
    const outputExtract = document.getElementById('extract_email');
    const outputMatched = document.getElementById('test_all');
    const lblExtract = document.getElementById('lbl_extract');
    const lblMatched = document.getElementById('lbl_matched');

    function process() {
      const allSmtpsText = inputSmtps.value;
      const goodScanText = inputScan.value;

      const extractedEmails = [];
      const smtpMap = new Map();

      if (allSmtpsText.trim()) {
        const lines = allSmtpsText.split(/\r?\n/);
        for (let line of lines) {
          const lineClean = line.trim();
          if (!lineClean) continue;

          const matches = lineClean.match(emailRegex);
          if (matches) {
            for (let email of matches) {
              const emailLower = email.toLowerCase();
              if (!smtpMap.has(emailLower)) {
                smtpMap.set(emailLower, lineClean);
              }
              if (!extractedEmails.includes(emailLower)) {
                extractedEmails.push(emailLower);
              }
            }
          }
        }
      }

      // Update Extract Output UI
      outputExtract.value = extractedEmails.join('\n');
      lblExtract.textContent = `2. EXTRACT_EMAIL (EXTRACTED: ${extractedEmails.length})`;

      // Match Logic
      const matchedSmtps = [];
      if (goodScanText.trim() && smtpMap.size > 0) {
        const scanMatches = goodScanText.match(emailRegex);
        const seenLines = new Set();
        if (scanMatches) {
          for (let scanEmail of scanMatches) {
            const emLower = scanEmail.toLowerCase();
            if (smtpMap.has(emLower)) {
              const fullLine = smtpMap.get(emLower);
              if (!seenLines.has(fullLine)) {
                seenLines.add(fullLine);
                matchedSmtps.push(fullLine);
              }
            }
          }
        }
      }

      // Update Matched Output UI
      outputMatched.value = matchedSmtps.join('\n');
      lblMatched.textContent = `4. TEST_ALL (MATCHED: ${matchedSmtps.length})`;
    }

    inputSmtps.addEventListener('input', process);
    inputScan.addEventListener('input', process);
  </script>
</body>
</html>
