<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FX Trader Simulator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0F172A; /* Deeper slate background */
            color: #E2E8F0;
            /* Added bull and bear background images with low opacity */
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill="%232D3748" fill-opacity="0.1" d="M75,50 C75,69.33 60.19,85 40,85 C20.19,85 5,69.33 5,50 C5,30.67 20.19,15 40,15 C60.19,15 75,30.67 75,50 z"/><path fill="%232D3748" fill-opacity="0.1" d="M25,50 C25,30.67 39.81,15 60,15 C79.81,15 95,30.67 95,50 C95,69.33 79.81,85 60,85 C39.81,85 25,69.33 25,50 z"/></svg>'), url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill="%232D3748" fill-opacity="0.1" d="M75,50 C75,69.33 60.19,85 40,85 C20.19,85 5,69.33 5,50 C5,30.67 20.19,15 40,15 C60.19,15 75,30.67 75,50 z"/><path fill="%232D3748" fill-opacity="0.1" d="M25,50 C25,30.67 39.81,15 60,15 C79.81,15 95,30.67 95,50 C95,69.33 79.81,85 60,85 C39.81,85 25,69.33 25,50 z"/></svg>');
            background-repeat: no-repeat, no-repeat;
            background-position: left top, right bottom;
            background-size: 30%, 30%;
        }
        .container {
            max-width: 1200px;
            margin: auto;
            padding: 2rem;
        }
        .card {
            background-color: #1E293B; /* Slightly lighter slate for cards */
            border-radius: 0.75rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
            padding: 1.5rem;
        }
        .glow-button {
            transition: all 0.3s ease;
            box-shadow: 0 4px 14px 0 rgba(0, 0, 0, 0.2);
        }
        .glow-button:hover {
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.7); /* Indigo glow on hover */
            transform: translateY(-2px);
        }
        .trend-reversal {
            background-color: #FBBF24;
            color: #1E293B;
        }
        .badge {
            font-weight: 600;
            text-transform: uppercase;
        }
        /* Custom styles for icon colors to match the theme */
        .icon {
            color: #64748B;
        }
    </style>
</head>
<body class="bg-slate-900 text-slate-200">

    <div class="container min-h-screen flex flex-col items-center">
        <header class="w-full text-center py-8">
            <h1 class="text-4xl font-extrabold text-indigo-400">FX Trader Simulator</h1>
            <p class="text-slate-400 mt-2 text-lg">A tool to monitor global macro conditions and get trade suggestions.</p>
        </header>

        <main class="w-full flex-1">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                <!-- Global Macro Conditions -->
                <div class="card">
                    <h2 class="text-2xl font-bold mb-4 text-center">Global Macro Conditions</h2>
                    <div id="macro-conditions" class="space-y-4">
                        <!-- Data will be populated here by JavaScript -->
                    </div>
                </div>

                <!-- Trade Suggestions -->
                <div class="card">
                    <h2 class="text-2xl font-bold mb-4 text-center">Trade Suggestions</h2>
                    <div id="trade-suggestions" class="space-y-6">
                        <!-- Suggestions will be populated here by JavaScript -->
                    </div>
                </div>
            </div>

            <!-- Market Headlines -->
            <div class="card my-8">
                <h2 class="text-2xl font-bold mb-4 text-center">Market Headlines</h2>
                <div id="market-headlines" class="text-xl font-semibold text-center text-blue-300">
                    <!-- Headlines will be populated here by JavaScript -->
                </div>
            </div>

            <div class="flex justify-center mt-4">
                <button id="analyze-button" class="glow-button bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-full transition duration-300">
                    Analyze Market
                </button>
            </div>
             <div id="weekend-status" class="mt-4 text-center"></div>
        </main>
    </div>

    <script>
        // Use a self-invoking function to avoid global variable pollution
        (function() {
            const macroData = {};
            const previousMacroData = {};
            const pairs = ['USD/JPY', 'EUR/USD', 'GBP/USD', 'USD/THB'];
            let marketHeadline = {}; // Now an object to hold both headlines

            // Function to generate a random number within a range
            const getRandom = (min, max) => Math.random() * (max - min) + min;

            // Function to simulate data for a specific region
            const generateRegionData = (region) => {
                const isUs = region === 'US';
                // Adjust base value for a more realistic THB simulation
                const baseValue = isUs ? 1.0 : (region === 'Thailand' ? 0.6 : 0.8);
                return {
                    gdp: getRandom(baseValue, baseValue + 0.5), // Simulated GDP Growth
                    cpi: getRandom(baseValue * 0.8, baseValue * 1.2), // Simulated CPI (Inflation)
                    unemployment: getRandom(baseValue * 1.5, baseValue * 2.5), // Simulated Unemployment Rate
                    interestRate: getRandom(baseValue * 3, baseValue * 5), // Simulated Interest Rate
                };
            };

            // Function to generate headlines based on US and THB macro data
            const generateHeadlines = (usData) => {
                const { gdp, unemployment, interestRate } = usData;
                const thData = macroData.thailand;
                
                let thHeadline = "เศรษฐกิจไทยมีแนวโน้มไม่ชัดเจน"; // Default Thai headline
                let enHeadline = "Economic data is mixed, markets await a clearer direction."; // Default English headline

                // Rules for THB headlines (in Thai)
                if (thData.gdp > 1.0 && thData.interestRate > 4.5) {
                    thHeadline = "เศรษฐกิจไทยเติบโตอย่างแข็งแกร่ง และธนาคารแห่งประเทศไทยปรับขึ้นอัตราดอกเบี้ยอย่างไม่คาดคิด ทำให้ค่าเงินบาทมีแนวโน้มแข็งค่าขึ้นเมื่อเทียบกับดอลลาร์สหรัฐฯ";
                } else if (thData.gdp < 0.7 && thData.unemployment > 2.0) {
                    thHeadline = "ข้อมูลเศรษฐกิจที่อ่อนแอของไทยทำให้ค่าเงินบาทมีแนวโน้มอ่อนค่าลงเมื่อเทียบกับดอลลาร์สหรัฐฯ";
                }

                // Rules for English headlines (based on USD data)
                if (gdp > 1.3 && interestRate > 4.5) {
                    enHeadline = "Federal Reserve to hike rates again amid strong GDP, boosting USD.";
                } else if (unemployment < 1.7 && gdp > 1.2) {
                    enHeadline = "US economy adds more jobs than expected; unemployment falls to new low.";
                } else if (interestRate > 4.0 && unemployment < 2.0) {
                    enHeadline = "USD strength soars as Fed hints at aggressive rate hikes.";
                } else if (gdp < 1.1 && unemployment > 2.0) {
                    enHeadline = "Recession fears rise as US GDP and employment data disappoint.";
                } else if (interestRate < 3.5 && unemployment > 2.3) {
                    enHeadline = "Fed considers rate cuts as inflation eases and labor market weakens.";
                } else if (gdp < 1.0) {
                    enHeadline = "US GDP growth slows unexpectedly, pressuring the US Dollar.";
                }

                return { english: enHeadline, thai: thHeadline };
            };

            // Function to refresh all simulated data
            const refreshData = () => {
                // Save a deep copy of the current data as previous data
                Object.assign(previousMacroData, macroData);

                macroData.us = generateRegionData('US');
                macroData.eurozone = generateRegionData('Europe');
                macroData.japan = generateRegionData('Japan');
                macroData.uk = generateRegionData('UK');
                macroData.thailand = generateRegionData('Thailand');
                marketHeadline = generateHeadlines(macroData.us);
                updateUI();
            };

            // Main function to analyze the data and provide trade suggestions
            const analyzeMarket = () => {
                // Check if it's the weekend
                const today = new Date();
                const dayOfWeek = today.getDay(); // 0 = Sunday, 6 = Saturday
                const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                
                if (isWeekend) {
                    const weekendSuggestions = {};
                    pairs.forEach(pair => {
                        weekendSuggestions[pair] = { action: 'Hold', reason: 'Market is closed for the weekend.', confidence: 0 };
                    });
                    return weekendSuggestions;
                }

                const suggestions = {};
                const usStrength = (macroData.us.gdp * 0.4) + (10 - macroData.us.unemployment) * 0.2 + (macroData.us.interestRate) * 0.4;
                const previousUsStrength = (previousMacroData.us?.gdp * 0.4) + (10 - previousMacroData.us?.unemployment) * 0.2 + (previousMacroData.us?.interestRate) * 0.4;

                // Simple rules-based analysis
                pairs.forEach(pair => {
                    let suggestion = { action: 'Hold', reason: 'No clear signal.', confidence: 0 };
                    let otherCountryData;
                    let previousOtherCountryData;

                    if (pair === 'USD/JPY') {
                        otherCountryData = macroData.japan;
                        previousOtherCountryData = previousMacroData.japan;
                        const jpyStrength = (otherCountryData.gdp * 0.3) + (10 - otherCountryData.unemployment) * 0.2 + (otherCountryData.interestRate) * 0.5;
                        const previousJpyStrength = (previousOtherCountryData?.gdp * 0.3) + (10 - previousOtherCountryData?.unemployment) * 0.2 + (previousOtherCountryData?.interestRate) * 0.5;
                        const relativeStrength = usStrength - jpyStrength;
                        const previousRelativeStrength = previousUsStrength - previousJpyStrength;

                        if (relativeStrength > 2) {
                            suggestion = { action: 'Buy', reason: 'Strong US economic data, particularly rising interest rates, suggests potential USD strength against the JPY.', confidence: 85 };
                        } else if (relativeStrength < -2) {
                            suggestion = { action: 'Sell', reason: 'Weak US economic data and potential rate cuts suggest USD weakness against the JPY.', confidence: 75 };
                        }

                        // Check for trend reversal
                        if (previousRelativeStrength > 1 && relativeStrength < -1) {
                            suggestion = { action: 'Trend Reversal', reason: 'A significant shift in economic data indicates a potential reversal from a USD-bullish to a USD-bearish trend.', confidence: 90 };
                        } else if (previousRelativeStrength < -1 && relativeStrength > 1) {
                            suggestion = { action: 'Trend Reversal', reason: 'A significant shift in economic data indicates a potential reversal from a USD-bearish to a USD-bullish trend.', confidence: 90 };
                        }
                    } else if (pair === 'EUR/USD') {
                        otherCountryData = macroData.eurozone;
                        previousOtherCountryData = previousMacroData.eurozone;
                        const eurStrength = (otherCountryData.gdp * 0.4) + (10 - otherCountryData.unemployment) * 0.2 + (otherCountryData.interestRate) * 0.4;
                        const previousEurStrength = (previousOtherCountryData?.gdp * 0.4) + (10 - previousOtherCountryData?.unemployment) * 0.2 + (previousOtherCountryData?.interestRate) * 0.4;
                        const relativeStrength = usStrength - eurStrength;
                        const previousRelativeStrength = previousUsStrength - previousEurStrength;

                        if (relativeStrength > 1) {
                            suggestion = { action: 'Sell', reason: 'The Eurozone economy is outperforming the US, which could lead to EUR strength and a drop in EUR/USD.', confidence: 80 };
                        } else if (relativeStrength < -1) {
                            suggestion = { action: 'Buy', reason: 'The US economy shows more positive momentum, signaling potential USD strength against the EUR.', confidence: 80 };
                        }

                        // Check for trend reversal
                        if (previousRelativeStrength > 0.5 && relativeStrength < -0.5) {
                             suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the EUR vs. USD suggests a trend reversal may be in effect.', confidence: 85 };
                        } else if (previousRelativeStrength < -0.5 && relativeStrength > 0.5) {
                             suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the EUR vs. USD suggests a trend reversal may be in effect.', confidence: 85 };
                        }
                    } else if (pair === 'GBP/USD') {
                        otherCountryData = macroData.uk;
                        previousOtherCountryData = previousMacroData.uk;
                        const gbpStrength = (otherCountryData.gdp * 0.4) + (10 - otherCountryData.unemployment) * 0.2 + (otherCountryData.interestRate) * 0.4;
                        const previousGbpStrength = (previousOtherCountryData?.gdp * 0.4) + (10 - previousOtherCountryData?.unemployment) * 0.2 + (previousOtherCountryData?.interestRate) * 0.4;
                        const relativeStrength = usStrength - gbpStrength;
                        const previousRelativeStrength = previousUsStrength - previousGbpStrength;
                        
                        if (relativeStrength > 1) {
                            suggestion = { action: 'Sell', reason: 'Strong UK economic data, including higher GDP and interest rates, points to potential GBP strength against the USD.', confidence: 70 };
                        } else if (relativeStrength < -1) {
                            suggestion = { action: 'Buy', reason: 'Weak UK economic data and potential rate cuts suggests GBP weakness against the USD.', confidence: 65 };
                        }

                         // Check for trend reversal
                        if (previousRelativeStrength > 0.5 && relativeStrength < -0.5) {
                            suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the GBP vs. USD suggests a trend reversal may be in effect.', confidence: 80 };
                        } else if (previousRelativeStrength < -0.5 && relativeStrength > 0.5) {
                             suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the GBP vs. USD suggests a trend reversal may be in effect.', confidence: 80 };
                        }
                    } else if (pair === 'USD/THB') {
                        otherCountryData = macroData.thailand;
                        previousOtherCountryData = previousMacroData.thailand;
                        const thbStrength = (otherCountryData.gdp * 0.3) + (10 - otherCountryData.unemployment) * 0.2 + (otherCountryData.interestRate) * 0.5;
                        const previousThbStrength = (previousOtherCountryData?.gdp * 0.3) + (10 - previousOtherCountryData?.unemployment) * 0.2 + (previousOtherCountryData?.interestRate) * 0.5;
                        const relativeStrength = usStrength - thbStrength;
                        const previousRelativeStrength = previousUsStrength - previousThbStrength;

                         if (relativeStrength > 1) {
                            suggestion = { action: 'Buy', reason: 'US macro conditions are stronger than Thailand’s, indicating potential USD strength against the THB.', confidence: 75 };
                        } else if (relativeStrength < -1) {
                            suggestion = { action: 'Sell', reason: 'Thailand’s economy is showing stronger momentum, suggesting potential THB strength against the USD.', confidence: 70 };
                        }

                        // Check for trend reversal
                        if (previousRelativeStrength > 0.5 && relativeStrength < -0.5) {
                             suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the USD vs. THB suggests a trend reversal may be in effect.', confidence: 85 };
                        } else if (previousRelativeStrength < -0.5 && relativeStrength > 0.5) {
                             suggestion = { action: 'Trend Reversal', reason: 'A sudden change in the relative strength of the USD vs. THB suggests a trend reversal may be in effect.', confidence: 85 };
                        }
                    }
                    suggestions[pair] = suggestion;
                });
                return suggestions;
            };

            // Function to update the UI with simulated data and trade suggestions
            const updateUI = () => {
                const macroDiv = document.getElementById('macro-conditions');
                const suggestionsDiv = document.getElementById('trade-suggestions');
                const headlinesDiv = document.getElementById('market-headlines');
                const weekendStatusDiv = document.getElementById('weekend-status');
                
                // Clear previous data
                macroDiv.innerHTML = '';
                suggestionsDiv.innerHTML = '';
                headlinesDiv.innerHTML = '';
                weekendStatusDiv.innerHTML = '';

                // Get trade suggestions
                const suggestions = analyzeMarket();

                // Display weekend status if applicable
                const isWeekend = suggestions['USD/JPY'].confidence === 0 && suggestions['USD/JPY'].action === 'Hold';
                if (isWeekend) {
                    weekendStatusDiv.innerHTML = `<span class="text-sm font-semibold text-slate-500 italic">Market Simulator is in weekend mode.</span>`;
                    // Don't show macro data on weekends
                    macroDiv.innerHTML = `<div class="card p-4 text-center text-slate-400">Market data is not available on weekends.</div>`;
                } else {
                    // Update Macro Conditions section
                    for (const region in macroData) {
                        const data = macroData[region];
                        const regionName = region.toUpperCase();
                        macroDiv.innerHTML += `
                            <div class="bg-slate-800 p-4 rounded-md">
                                <h3 class="text-xl font-semibold mb-2">${regionName}</h3>
                                <ul class="text-slate-400 text-sm space-y-1">
                                    <li><strong>GDP Growth:</strong> ${data.gdp.toFixed(2)}%</li>
                                    <li><strong>CPI (Inflation):</strong> ${data.cpi.toFixed(2)}%</li>
                                    <li><strong>Unemployment Rate:</strong> ${data.unemployment.toFixed(2)}%</li>
                                    <li><strong>Interest Rate:</strong> ${data.interestRate.toFixed(2)}%</li>
                                </ul>
                            </div>
                        `;
                    }
                }


                // Update Trade Suggestions section
                for (const pair in suggestions) {
                    const suggestion = suggestions[pair];
                    const actionClass = suggestion.action === 'Buy' ? 'bg-green-600' : (suggestion.action === 'Sell' ? 'bg-red-600' : (suggestion.action === 'Trend Reversal' ? 'bg-amber-400' : 'bg-slate-600'));
                    suggestionsDiv.innerHTML += `
                        <div class="card p-4 flex flex-col items-center text-center">
                            <div class="flex items-center space-x-2">
                                <span class="text-2xl font-bold">${pair}</span>
                                <span class="badge px-3 py-1 rounded-full ${actionClass} text-white">${suggestion.action}</span>
                            </div>
                            <p class="text-sm text-slate-400 mt-2">${suggestion.reason}</p>
                            <span class="text-xs text-slate-500 mt-2">Confidence Score: ${suggestion.confidence}%</span>
                        </div>
                    `;
                }

                // Update Market Headlines section with both English and Thai headlines
                headlinesDiv.innerHTML = `
                    <div class="text-xl font-semibold text-center text-indigo-300 mb-2">${marketHeadline.english}</div>
                    <div class="text-base font-medium text-center text-slate-400">${marketHeadline.thai}</div>
                `;
            };

            // Event listener for the "Analyze Market" button
            document.getElementById('analyze-button').addEventListener('click', () => {
                refreshData();
            });

            // Initial data load on page load
            window.onload = refreshData;

        })();
    </script>
</body>
</html>
