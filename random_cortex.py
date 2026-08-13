<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Header & Random Tag Converter</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        header {
            background-color: #252526;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #3c3c3c;
        }
        header h1 {
            font-size: 16px;
            color: #61afef;
            font-weight: 600;
        }
        .controls {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .input-group {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }
        .input-group label {
            color: #abb2bf;
        }
        .input-group input {
            background: #3c3c3c;
            border: 1px solid #555;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            outline: none;
        }
        button {
            background-color: #0e639c;
            color: white;
            border: none;
            padding: 6px 14px;
            font-size: 13px;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background-color: #1177bb;
        }
        .copy-btn {
            background-color: #388e3c;
        }
        .copy-btn:hover {
            background-color: #2e7d32;
        }
        .container {
            display: flex;
            flex: 1;
            height: calc(100vh - 50px);
        }
        .editor-box {
            flex: 1;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #3c3c3c;
            position: relative;
        }
        .editor-header {
            background-color: #2d2d2d;
            padding: 6px 12px;
            font-size: 12px;
            color: #9cdcfe;
            font-weight: bold;
            border-bottom: 1px solid #3c3c3c;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        textarea {
            flex: 1;
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            outline: none;
            padding: 15px;
            font-family: "Courier New", Courier, monospace;
            font-size: 13px;
            line-height: 1.5;
            resize: none;
            white-space: pre;
            overflow-x: auto;
        }
        textarea::placeholder {
            color: #5c6370;
        }
    </style>
</head>
<body>

    <header>
        <h1>⚡ Header & Tag Converter Tool</h1>
        <div class="controls">
            <div class="input-group">
                <label for="recipientEmail">Recipient [to]:</label>
                <input type="text" id="recipientEmail" placeholder="top841379@gmail.com">
            </div>
            <div class="input-group">
                <label for="mainDomain">Domain [placeholder5]:</label>
                <input type="text" id="mainDomain" placeholder="dgribpvmepad-ewtyhw.org">
            </div>
            <button onclick="convertText()">Convert Now 🚀</button>
            <button class="copy-btn" onclick="copyOutput()">Copy Output 📋</button>
        </div>
    </header>

    <div class="container">
        <!-- Left Input Panel -->
        <div class="editor-box">
            <div class="editor-header">Input (Raw Text / Headers / Randoms)</div>
            <textarea id="inputText" placeholder="Paste your raw email, headers, or HTML with random strings here..."></textarea>
        </div>

        <!-- Right Output Panel -->
        <div class="editor-box">
            <div class="editor-header">Output (Converted Tags)</div>
            <textarea id="outputText" readonly placeholder="Converted text with tags will appear here automatically..."></textarea>
        </div>
    </div>

    <script>
        function detectPatternTag(token) {
            if (!token || !/^[a-zA-Z0-9]+$/.test(token)) return token;

            const len = token.length;
            const hasDigit = /\d/.test(token);
            const hasLower = /[a-z]/.test(token);
            const hasUpper = /[A-Z]/.test(token);

            // Pure Numbers -> (n,x)
            if (/^\d+$/.test(token)) return `(n,${len})`;

            // Pure Lowercase -> (a,x)
            if (/^[a-z]+$/.test(token) && !hasDigit) return `(a,${len})`;

            // Pure Uppercase -> (A,x)
            if (/^[A-Z]+$/.test(token) && !hasDigit) return `(A,${len})`;

            // Mixed Case Alpha -> (Aa,x)
            if (/^[a-zA-Z]+$/.test(token) && hasLower && hasUpper) return `(Aa,${len})`;

            // Lowercase + Numbers -> (an,x)
            if (hasDigit && hasLower && !hasUpper) return `(an,${len})`;

            // Uppercase + Numbers -> (An,x)
            if (hasDigit && hasUpper && !hasLower) return `(An,${len})`;

            // Mixed Alpha + Numbers -> (aAn,x)
            if (hasDigit && hasLower && hasUpper) return `(aAn,${len})`;

            return token;
        }

        function convertText() {
            let text = document.getElementById("inputText").value;
            const recipientEmail = document.getElementById("recipientEmail").value.trim();
            const mainDomain = document.getElementById("mainDomain").value.trim();

            if (!text) {
                document.getElementById("outputText").value = "";
                return;
            }

            // 1. Replace SMTP Dates with [smtp_date]
            const smtpDateRegex = /(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+[\+\-]\d{4}/gi;
            text = text.replace(smtpDateRegex, '[smtp_date]');

            // 2. Replace Target Email if provided
            if (recipientEmail) {
                text = text.replaceAll(recipientEmail, '[to]');
            }

            // 3. Replace Main Domain if provided
            if (mainDomain) {
                text = text.replaceAll(mainDomain, '[placeholder5]');
            }

            // 4. Token Replacement for Random Strings
            text = text.replace(/\b[a-zA-Z0-9]{5,}\b/g, (match) => {
                // If it contains digits or is long random string or upper case random string
                if (/\d/.test(match) || match.length >= 10 || match === match.toUpperCase()) {
                    return detectPatternTag(match);
                }
                return match;
            });

            document.getElementById("outputText").value = text;
        }

        // Real-time conversion on input
        document.getElementById("inputText").addEventListener("input", convertText);

        function copyOutput() {
            const output = document.getElementById("outputText");
            if (!output.value) return;
            output.select();
            document.execCommand("copy");
            alert("Copied to clipboard!");
        }
    </script>
</body>
</html>