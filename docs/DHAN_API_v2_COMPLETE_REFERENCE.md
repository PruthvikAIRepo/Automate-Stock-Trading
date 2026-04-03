# Dhan API v2 — Complete Reference for StockPulse

> **Base URL (Production):** `https://api.dhan.co`
> **Base URL (Sandbox):** `https://sandbox.dhan.co`
> **Auth Server:** `https://auth.dhan.co`
> **Web Portal:** `https://web.dhan.co`

---

## Table of Contents

1. [Postman Setup](#1-postman-setup)
2. [Authentication](#2-authentication)
3. [Orders](#3-orders)
4. [Super Orders](#4-super-orders)
5. [Forever Orders (GTT/GTC)](#5-forever-orders-gttgtc)
6. [Conditional Triggers](#6-conditional-triggers)
7. [Portfolio](#7-portfolio)
8. [Funds & Margin](#8-funds--margin)
9. [Trader's Control](#9-traders-control)
10. [Statements](#10-statements)
11. [Market Quote (REST)](#11-market-quote-rest)
12. [Historical Data](#12-historical-data)
13. [Option Chain](#13-option-chain)
14. [Expired Options Data](#14-expired-options-data)
15. [Live Market Feed (WebSocket)](#15-live-market-feed-websocket)
16. [Full Market Depth (WebSocket)](#16-full-market-depth-websocket)
17. [EDIS](#17-edis)
18. [Enums & Error Codes](#18-enums--error-codes)
19. [Rate Limits](#19-rate-limits)

---

## 1. Postman Setup

### Step 1: Create Postman Environment

Create a new environment called **"Dhan API v2"** with these variables:

| Variable | Type | Initial Value | Description |
|----------|------|---------------|-------------|
| `base_url` | default | `https://api.dhan.co` | Production API base |
| `sandbox_url` | default | `https://sandbox.dhan.co` | Sandbox API base |
| `auth_url` | default | `https://auth.dhan.co` | Auth server base |
| `access_token` | secret | *(your JWT)* | 24-hour access token |
| `client_id` | default | *(your Dhan client ID)* | e.g. `1000000003` |
| `security_id_reliance` | default | `2885` | RELIANCE security ID |
| `security_id_tcs` | default | `11536` | TCS security ID |
| `security_id_hdfcbank` | default | `1333` | HDFCBANK security ID |
| `security_id_nifty` | default | `13` | NIFTY 50 index ID |
| `order_id` | default | *(auto-set by tests)* | Last placed order ID |

### Step 2: Common Headers (apply to all requests)

In Postman, create a **Collection** called "Dhan API v2" and set these collection-level headers:

```
Content-Type: application/json
Accept: application/json
access-token: {{access_token}}
```

Some endpoints also require:
```
client-id: {{client_id}}
```

### Step 3: Get Your Access Token

**Option A — Manual (quickest for testing):**
1. Go to https://web.dhan.co
2. Navigate to DhanHQ Trading APIs section
3. Generate access token (valid 24 hours)
4. Paste into Postman environment variable `access_token`

**Option B — Via TOTP API:**
```
POST {{auth_url}}/app/generateAccessToken
```
```json
{
    "dhanClientId": "{{client_id}}",
    "pin": "123456",
    "totp": "789012"
}
```
Response:
```json
{
    "dhanClientId": "1000000003",
    "dhanClientName": "Pruthvik",
    "accessToken": "eyJhbGci...",
    "expiryTime": "2026-03-31T10:00:00"
}
```

**Auto-save token in Postman Tests tab:**
```javascript
if (pm.response.code === 200) {
    var json = pm.response.json();
    pm.environment.set("access_token", json.accessToken);
}
```

### Step 4: Set Static IP (required for order APIs)

```
POST {{base_url}}/v2/ip/setIP
```
- Once set, cannot be modified for 7 days
- Supports IPv4 and IPv6
- Only required for order placement/modify/cancel endpoints

Check current IP:
```
GET {{base_url}}/v2/ip/getIP
```

### Step 5: Verify Profile

```
GET {{base_url}}/v2/profile
```
Response includes: `tokenValidity`, `activeSegment`, `ddpi_status`, `mtf_status`, `dataPlan_status`

---

## 2. Authentication

### 2.1 Generate Token via TOTP

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{auth_url}}/app/generateAccessToken` |
| **Headers** | `Content-Type: application/json` |

```json
{
    "dhanClientId": "{{client_id}}",
    "pin": "123456",
    "totp": "789012"
}
```

**Response:**
```json
{
    "dhanClientId": "1000000003",
    "dhanClientName": "Pruthvik",
    "dhanClientUcc": "1000000003",
    "givenPowerOfAttorney": false,
    "accessToken": "eyJhbGci...",
    "expiryTime": "2026-03-31T10:00:00"
}
```

### 2.2 Renew Token

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/RenewToken` |
| **Headers** | `access-token: {{access_token}}`, `dhanClientId: {{client_id}}` |

> Only works on active (non-expired) tokens. Extends by 24 hours.

### 2.3 OAuth Flow (API Key + Secret)

**Step 1 — Generate Consent:**
```
POST {{auth_url}}/app/generate-consent?client_id={{client_id}}
Headers: app_id: <API_KEY>, app_secret: <API_SECRET>
```
Response: `{ "consentAppId": "abc123", "consentAppStatus": "GENERATED" }`

**Step 2 — Browser redirect:**
`https://auth.dhan.co/login/consentApp-login?consentAppId=abc123`
User logs in → redirected to your URL with `tokenId`

**Step 3 — Consume Consent:**
```
GET {{auth_url}}/app/consumeApp-consent?tokenId=<tokenId>
Headers: app_id: <API_KEY>, app_secret: <API_SECRET>
```
Response: same as TOTP response (includes `accessToken`)

---

## 3. Orders

### 3.1 Place Order

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/orders` |
| **IP Whitelist** | Required |

```json
{
    "dhanClientId": "{{client_id}}",
    "correlationId": "my-order-001",
    "transactionType": "BUY",
    "exchangeSegment": "NSE_EQ",
    "productType": "INTRADAY",
    "orderType": "MARKET",
    "validity": "DAY",
    "securityId": "{{security_id_reliance}}",
    "quantity": 1,
    "disclosedQuantity": "",
    "price": "",
    "triggerPrice": "",
    "afterMarketOrder": false,
    "amoTime": "",
    "boProfitValue": "",
    "boStopLossValue": ""
}
```

**Request Fields:**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `dhanClientId` | string | Yes | Your client ID |
| `correlationId` | string | No | Max 30 chars `[a-zA-Z0-9 _-]` |
| `transactionType` | enum | Yes | `BUY`, `SELL` |
| `exchangeSegment` | enum | Yes | `NSE_EQ`, `NSE_FNO`, `NSE_CURRENCY`, `BSE_EQ`, `BSE_FNO`, `BSE_CURRENCY`, `MCX_COMM` |
| `productType` | enum | Yes | `CNC`, `INTRADAY`, `MARGIN`, `MTF`, `CO`, `BO` |
| `orderType` | enum | Yes | `LIMIT`, `MARKET`, `STOP_LOSS`, `STOP_LOSS_MARKET` |
| `validity` | enum | Yes | `DAY`, `IOC` |
| `securityId` | string | Yes | Exchange security ID |
| `quantity` | int | Yes | Number of shares |
| `disclosedQuantity` | int | No | Must be >30% of quantity |
| `price` | float | Yes* | Required for LIMIT, STOP_LOSS |
| `triggerPrice` | float | Cond. | Required for STOP_LOSS, STOP_LOSS_MARKET |
| `afterMarketOrder` | boolean | No | `true`/`false` |
| `amoTime` | enum | Cond. | `PRE_OPEN`, `OPEN`, `OPEN_30`, `OPEN_60` (when AMO=true) |
| `boProfitValue` | float | Cond. | Bracket Order target |
| `boStopLossValue` | float | Cond. | Bracket Order stop loss |

**Response:**
```json
{
    "orderId": "112111182198",
    "orderStatus": "PENDING"
}
```

**Postman Tests (auto-save orderId):**
```javascript
if (pm.response.code === 200) {
    pm.environment.set("order_id", pm.response.json().orderId);
}
```

### 3.2 Modify Order

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `{{base_url}}/v2/orders/{{order_id}}` |

```json
{
    "dhanClientId": "{{client_id}}",
    "orderId": "{{order_id}}",
    "orderType": "LIMIT",
    "legName": "",
    "quantity": 5,
    "price": 2800.50,
    "disclosedQuantity": "",
    "triggerPrice": "",
    "validity": "DAY"
}
```

### 3.3 Cancel Order

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/orders/{{order_id}}` |
| **Body** | None |
| **Response** | 202 Accepted |

```json
{ "orderId": "112111182045", "orderStatus": "CANCELLED" }
```

### 3.4 Slice Order

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/orders/slicing` |

Body: Same structure as Place Order (3.1)

### 3.5 Get All Orders (Order Book)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/orders` |
| **Body** | None |

**Response (array):**
```json
[
    {
        "dhanClientId": "1000000003",
        "orderId": "112111182198",
        "correlationId": "my-order-001",
        "orderStatus": "PENDING",
        "transactionType": "BUY",
        "exchangeSegment": "NSE_EQ",
        "productType": "INTRADAY",
        "orderType": "MARKET",
        "validity": "DAY",
        "tradingSymbol": "",
        "securityId": "11536",
        "quantity": 5,
        "disclosedQuantity": 0,
        "price": 0.0,
        "triggerPrice": 0.0,
        "afterMarketOrder": false,
        "boProfitValue": 0.0,
        "boStopLossValue": 0.0,
        "legName": null,
        "createTime": "2021-11-24 13:33:03",
        "updateTime": "2021-11-24 13:33:03",
        "exchangeTime": "2021-11-24 13:33:03",
        "drvExpiryDate": null,
        "drvOptionType": null,
        "drvStrikePrice": 0.0,
        "omsErrorCode": null,
        "omsErrorDescription": null,
        "algoId": "",
        "remainingQuantity": 5,
        "averageTradedPrice": 0,
        "filledQty": 0
    }
]
```

### 3.6 Get Order by ID

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/orders/{{order_id}}` |

### 3.7 Get Order by Correlation ID

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/orders/external/my-order-001` |

### 3.8 Get All Trades (Trade Book)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/trades` |

**Response (array):**
```json
[
    {
        "dhanClientId": "1000000009",
        "orderId": "112111182045",
        "exchangeOrderId": "15112111182045",
        "exchangeTradeId": "15112111182045",
        "transactionType": "BUY",
        "exchangeSegment": "NSE_EQ",
        "productType": "INTRADAY",
        "orderType": "LIMIT",
        "tradingSymbol": "TCS",
        "securityId": "11536",
        "tradedQuantity": 40,
        "tradedPrice": 3345.8,
        "createTime": "2021-03-10 11:20:06",
        "updateTime": "2021-11-25 17:35:12",
        "exchangeTime": "2021-11-25 17:35:12",
        "drvExpiryDate": null,
        "drvOptionType": null,
        "drvStrikePrice": 0.0
    }
]
```

### 3.9 Get Trades for Order

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/trades/{{order_id}}` |

---

## 4. Super Orders

Super Orders combine entry + target + stop loss in one order with optional trailing.

### 4.1 Place Super Order

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/super/orders` |

```json
{
    "dhanClientId": "{{client_id}}",
    "correlationId": "super-001",
    "transactionType": "BUY",
    "exchangeSegment": "NSE_EQ",
    "productType": "CNC",
    "orderType": "LIMIT",
    "securityId": "{{security_id_hdfcbank}}",
    "quantity": 5,
    "price": 1500,
    "targetPrice": 1600,
    "stopLossPrice": 1400,
    "trailingJump": 10
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `productType` | enum | Yes | `CNC`, `INTRADAY`, `MARGIN`, `MTF` (no CO/BO) |
| `orderType` | enum | Yes | `LIMIT`, `MARKET` only (no SL) |
| `targetPrice` | float | Yes | Take profit price |
| `stopLossPrice` | float | Yes | Stop loss price |
| `trailingJump` | float | Yes | Trail amount (0 = no trailing) |

### 4.2 Modify Super Order

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `{{base_url}}/v2/super/orders/{{order_id}}` |

**Modify Entry Leg** (only when PENDING/PART_TRADED):
```json
{
    "dhanClientId": "{{client_id}}",
    "orderId": "{{order_id}}",
    "orderType": "LIMIT",
    "legName": "ENTRY_LEG",
    "quantity": 10,
    "price": 1300,
    "targetPrice": 1450,
    "stopLossPrice": 1200,
    "trailingJump": 20
}
```

**Modify Target Leg** (after TRADED):
```json
{
    "dhanClientId": "{{client_id}}",
    "orderId": "{{order_id}}",
    "legName": "TARGET_LEG",
    "targetPrice": 1450
}
```

**Modify Stop Loss Leg** (after TRADED):
```json
{
    "dhanClientId": "{{client_id}}",
    "orderId": "{{order_id}}",
    "legName": "STOP_LOSS_LEG",
    "stopLossPrice": 1350,
    "trailingJump": 20
}
```

### 4.3 Cancel Super Order

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/super/orders/{{order_id}}/ENTRY_LEG` |

Path: `/{order-id}/{leg}` — leg = `ENTRY_LEG`, `TARGET_LEG`, or `STOP_LOSS_LEG`

> Cancelling ENTRY_LEG cancels ALL legs. Cancelled target/SL legs cannot be re-added.

### 4.4 Get All Super Orders

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/super/orders` |

Response includes `legDetails` array with nested target/SL leg info.

---

## 5. Forever Orders (GTT/GTC)

Good Till Triggered / Good Till Cancelled orders.

### 5.1 Create Forever Order

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/forever/orders` |

**Single leg (GTT):**
```json
{
    "dhanClientId": "{{client_id}}",
    "correlationId": "",
    "orderFlag": "SINGLE",
    "transactionType": "BUY",
    "exchangeSegment": "NSE_EQ",
    "productType": "CNC",
    "orderType": "LIMIT",
    "validity": "DAY",
    "securityId": "{{security_id_hdfcbank}}",
    "quantity": 5,
    "disclosedQuantity": 0,
    "price": 1428,
    "triggerPrice": 1427
}
```

**OCO (One Cancels Other):**
```json
{
    "dhanClientId": "{{client_id}}",
    "orderFlag": "OCO",
    "transactionType": "BUY",
    "exchangeSegment": "NSE_EQ",
    "productType": "CNC",
    "orderType": "LIMIT",
    "validity": "DAY",
    "securityId": "{{security_id_hdfcbank}}",
    "quantity": 5,
    "disclosedQuantity": 1,
    "price": 1428,
    "triggerPrice": 1427,
    "price1": 1420,
    "triggerPrice1": 1419,
    "quantity1": 10
}
```

| Field | Type | Notes |
|-------|------|-------|
| `orderFlag` | enum | `SINGLE` or `OCO` |
| `productType` | enum | `CNC`, `MTF` only |
| `exchangeSegment` | enum | `NSE_EQ`, `NSE_FNO`, `BSE_EQ`, `MCX_COMM` |
| `price1`, `triggerPrice1`, `quantity1` | float/int | OCO only — second leg |

### 5.2 Modify Forever Order

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `{{base_url}}/v2/forever/orders/{{order_id}}` |

```json
{
    "dhanClientId": "{{client_id}}",
    "orderId": "{{order_id}}",
    "orderFlag": "SINGLE",
    "orderType": "LIMIT",
    "legName": "TARGET_LEG",
    "quantity": 15,
    "price": 1421,
    "disclosedQuantity": 1,
    "triggerPrice": 1420,
    "validity": "DAY"
}
```

### 5.3 Delete Forever Order

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/forever/orders/{{order_id}}` |

### 5.4 Get All Forever Orders

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/forever/all` |

---

## 6. Conditional Triggers

Alert-based orders triggered by technical indicators.

### 6.1 Create Trigger

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/alerts/orders` |

```json
{
    "dhanClientId": "{{client_id}}",
    "condition": {
        "comparisonType": "TECHNICAL_WITH_VALUE",
        "exchangeSegment": "NSE_EQ",
        "securityId": "{{security_id_reliance}}",
        "indicatorName": "SMA_5",
        "timeFrame": "DATE",
        "operator": "CROSSING_UP",
        "comparingValue": 2800,
        "expDate": "2026-12-31",
        "frequency": "ONCE",
        "userNote": "Buy when SMA5 crosses 2800"
    },
    "orders": [
        {
            "transactionType": "BUY",
            "exchangeSegment": "NSE_EQ",
            "productType": "CNC",
            "orderType": "LIMIT",
            "securityId": "{{security_id_reliance}}",
            "quantity": 10,
            "validity": "DAY",
            "price": "2800.00",
            "discQuantity": "0",
            "triggerPrice": "0"
        }
    ]
}
```

**Condition Fields:**

| Field | Type | Values |
|-------|------|--------|
| `comparisonType` | enum | `TECHNICAL_WITH_VALUE`, `TECHNICAL_WITH_INDICATOR`, `TECHNICAL_WITH_CLOSE`, `PRICE_WITH_VALUE` |
| `exchangeSegment` | enum | `NSE_EQ`, `BSE_EQ`, `IDX_I` only |
| `indicatorName` | enum | `SMA_5/10/20/50/100/200`, `EMA_5/10/20/50/100/200`, `BB_UPPER`, `BB_LOWER`, `RSI_14`, `ATR_14`, `STOCHASTIC`, `STOCHRSI_14`, `MACD_26`, `MACD_12`, `MACD_HIST` |
| `timeFrame` | enum | `DATE`, `ONE_MIN`, `FIVE_MIN`, `FIFTEEN_MIN` |
| `operator` | enum | `CROSSING_UP`, `CROSSING_DOWN`, `CROSSING_ANY_SIDE`, `GREATER_THAN`, `LESS_THAN`, `GREATER_THAN_EQUAL`, `LESS_THAN_EQUAL`, `EQUAL`, `NOT_EQUAL` |
| `frequency` | enum | `ONCE` |

**Response:**
```json
{ "alertId": "12345", "alertStatus": "ACTIVE" }
```

### 6.2 Modify Trigger

| | |
|---|---|
| **Method** | `PUT` |
| **URL** | `{{base_url}}/v2/alerts/orders/{alertId}` |

### 6.3 Cancel Trigger

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/alerts/orders/{alertId}` |

### 6.4 Get Trigger by ID

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/alerts/orders/{alertId}` |

### 6.5 Get All Triggers

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/alerts/orders` |

**Trigger Statuses:** `ACTIVE`, `TRIGGERED`, `EXPIRED`, `CANCELLED`

---

## 7. Portfolio

### 7.1 Get Holdings

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/holdings` |

**Response:**
```json
[
    {
        "exchange": "ALL",
        "tradingSymbol": "HDFC",
        "securityId": "1330",
        "isin": "INE001A01036",
        "totalQty": 1000,
        "dpQty": 1000,
        "t1Qty": 0,
        "availableQty": 1000,
        "collateralQty": 0,
        "avgCostPrice": 2655.0
    }
]
```

### 7.2 Get Positions

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/positions` |

**Response:**
```json
[
    {
        "dhanClientId": "1000000009",
        "tradingSymbol": "TCS",
        "securityId": "11536",
        "positionType": "LONG",
        "exchangeSegment": "NSE_EQ",
        "productType": "CNC",
        "buyAvg": 3345.8,
        "buyQty": 40,
        "costPrice": 3215.0,
        "sellAvg": 0.0,
        "sellQty": 0,
        "netQty": 40,
        "realizedProfit": 0.0,
        "unrealizedProfit": 6122.0,
        "rbiReferenceRate": 1.0,
        "multiplier": 1,
        "carryForwardBuyQty": 0,
        "carryForwardSellQty": 0,
        "carryForwardBuyValue": 0.0,
        "carryForwardSellValue": 0.0,
        "dayBuyQty": 40,
        "daySellQty": 0,
        "dayBuyValue": 133832.0,
        "daySellValue": 0.0,
        "drvExpiryDate": "0001-01-01",
        "drvOptionType": null,
        "drvStrikePrice": 0.0,
        "crossCurrency": false
    }
]
```

### 7.3 Convert Position

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/positions/convert` |

```json
{
    "dhanClientId": "{{client_id}}",
    "fromProductType": "INTRADAY",
    "exchangeSegment": "NSE_EQ",
    "positionType": "LONG",
    "securityId": "{{security_id_tcs}}",
    "tradingSymbol": "",
    "convertQty": 40,
    "toProductType": "CNC"
}
```
Response: `202 Accepted`

### 7.4 Exit All Positions

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/positions` |

```json
{ "status": "SUCCESS", "message": "All orders and positions exited successfully" }
```

---

## 8. Funds & Margin

### 8.1 Single Order Margin Calculator

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/margincalculator` |

```json
{
    "dhanClientId": "{{client_id}}",
    "exchangeSegment": "NSE_EQ",
    "transactionType": "BUY",
    "quantity": 5,
    "productType": "CNC",
    "securityId": "{{security_id_hdfcbank}}",
    "price": 1428,
    "triggerPrice": 0
}
```

**Response:**
```json
{
    "totalMargin": 2800.00,
    "spanMargin": 1200.00,
    "exposureMargin": 1003.00,
    "availableBalance": 10500.00,
    "variableMargin": 1000.00,
    "insufficientBalance": 0.00,
    "brokerage": 20.00,
    "leverage": "4.00"
}
```

### 8.2 Multi-Order Margin Calculator

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/margincalculator/multi` |

```json
{
    "includePosition": true,
    "includeOrders": true,
    "scripts": [
        {
            "exchangeSegment": "NSE_EQ",
            "transactionType": "BUY",
            "quantity": 100,
            "productType": "CNC",
            "securityId": "{{security_id_hdfcbank}}",
            "price": 1500
        }
    ]
}
```

### 8.3 Get Fund Limit

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/fundlimit` |

**Response:**
```json
{
    "dhanClientId": "1000000009",
    "availabelBalance": 98440.0,
    "sodLimit": 113642,
    "collateralAmount": 0.0,
    "receiveableAmount": 0.0,
    "utilizedAmount": 15202.0,
    "blockedPayoutAmount": 0.0,
    "withdrawableBalance": 98310.0
}
```

> Note: `availabelBalance` is a typo in the official API (missing 'l').

---

## 9. Trader's Control

### 9.1 Activate Kill Switch

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/killswitch?killSwitchStatus=ACTIVATE` |

> All positions must be closed and no pending orders before activation.

### 9.2 Deactivate Kill Switch

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/killswitch?killSwitchStatus=DEACTIVATE` |

### 9.3 Get Kill Switch Status

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/killswitch` |

### 9.4 Set P&L Based Exit

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/pnlExit` |

```json
{
    "profitValue": "1500.00",
    "lossValue": "500.00",
    "productType": ["INTRADAY", "DELIVERY"],
    "enableKillSwitch": true
}
```

> Active for current day only. Resets at end of trading session.

### 9.5 Stop P&L Based Exit

| | |
|---|---|
| **Method** | `DELETE` |
| **URL** | `{{base_url}}/v2/pnlExit` |

### 9.6 Get P&L Exit Status

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/pnlExit` |

---

## 10. Statements

### 10.1 Ledger Report

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/ledger?from-date=2026-01-01&to-date=2026-03-30` |

**Response:**
```json
{
    "dhanClientId": "1000000001",
    "narration": "FUNDS WITHDRAWAL",
    "voucherdate": "Jun 22, 2022",
    "exchange": "NSE-CAPITAL",
    "voucherdesc": "PAYBNK",
    "vouchernumber": "202200036701",
    "debit": "20000.00",
    "credit": "0.00",
    "runbal": "957.29"
}
```

### 10.2 Trade History

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/trades/2026-01-01/2026-03-30/0` |

Path: `/v2/trades/{from-date}/{to-date}/{page}` — page `0` is default, response is paginated.

---

## 11. Market Quote (REST)

> **Extra header required:** `client-id: {{client_id}}`
> **Rate limit:** 1 req/sec, up to 1000 instruments per request

### 11.1 LTP (Last Traded Price)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/marketfeed/ltp` |
| **Headers** | `access-token`, `client-id`, `Content-Type` |

```json
{
    "NSE_EQ": [2885, 11536, 1333],
    "BSE_EQ": [500325]
}
```

**Response:**
```json
{
    "data": {
        "NSE_EQ": {
            "2885": { "last_price": 2856.50 },
            "11536": { "last_price": 4520.00 },
            "1333": { "last_price": 1660.95 }
        }
    },
    "status": "success"
}
```

### 11.2 OHLC

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/marketfeed/ohlc` |

Same request body format. Response adds `ohlc: { open, close, high, low }`.

### 11.3 Full Quote (with Market Depth)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/marketfeed/quote` |

Same request body format. Response includes: `average_price`, `buy_quantity`, `sell_quantity`, `depth` (5 levels buy/sell), `last_price`, `last_quantity`, `last_trade_time`, `lower_circuit_limit`, `upper_circuit_limit`, `net_change`, `ohlc`, `oi`, `volume`.

---

## 12. Historical Data

### 12.1 Daily Candles

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/charts/historical` |

```json
{
    "securityId": "{{security_id_hdfcbank}}",
    "exchangeSegment": "NSE_EQ",
    "instrument": "EQUITY",
    "expiryCode": 0,
    "oi": false,
    "fromDate": "2026-01-01",
    "toDate": "2026-03-30"
}
```

**Response:**
```json
{
    "open": [3978, 3856, 3925],
    "high": [3978, 3925, 3929],
    "low": [3861, 3856, 3836.55],
    "close": [3879.85, 3915.9, 3859.9],
    "volume": [3937092, 1906106, 3203744],
    "timestamp": [1326220200, 1326306600, 1326393000],
    "open_interest": [0, 0, 0]
}
```

| Field | Type | Values |
|-------|------|--------|
| `instrument` | enum | `INDEX`, `FUTIDX`, `OPTIDX`, `EQUITY`, `FUTSTK`, `OPTSTK`, `FUTCOM`, `OPTFUT`, `FUTCUR`, `OPTCUR` |
| `expiryCode` | int | `0` (Current), `1` (Next), `2` (Far) |

### 12.2 Intraday Candles

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/charts/intraday` |

```json
{
    "securityId": "{{security_id_hdfcbank}}",
    "exchangeSegment": "NSE_EQ",
    "instrument": "EQUITY",
    "interval": "5",
    "oi": false,
    "fromDate": "2026-03-28 09:15:00",
    "toDate": "2026-03-28 15:30:00"
}
```

| Field | Values |
|-------|--------|
| `interval` | `1`, `5`, `15`, `25`, `60` (minutes) |

> Max 90 days per API call. Data available for last 5 years.

---

## 13. Option Chain

### 13.1 Get Option Chain

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/optionchain` |
| **Headers** | `access-token`, `client-id`, `Content-Type` |
| **Rate Limit** | 1 req per 3 seconds per underlying/expiry |

```json
{
    "UnderlyingScrip": 13,
    "UnderlyingSeg": "IDX_I",
    "Expiry": "2026-04-24"
}
```

**Response:**
```json
{
    "data": {
        "last_price": 25642.8,
        "oc": {
            "25650.000000": {
                "ce": {
                    "average_price": 146.99,
                    "greeks": {
                        "delta": 0.53871,
                        "theta": -15.1539,
                        "gamma": 0.00132,
                        "vega": 12.18593
                    },
                    "implied_volatility": 9.789,
                    "last_price": 134,
                    "oi": 3786445,
                    "previous_close_price": 244.85,
                    "previous_oi": 402220,
                    "previous_volume": 31931705,
                    "security_id": 42528,
                    "top_ask_price": 134,
                    "top_ask_quantity": 1365,
                    "top_bid_price": 133.55,
                    "top_bid_quantity": 1625,
                    "volume": 117567970
                },
                "pe": { "..." : "same structure" }
            }
        }
    },
    "status": "success"
}
```

### 13.2 Get Expiry List

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/optionchain/expirylist` |

```json
{
    "UnderlyingScrip": 13,
    "UnderlyingSeg": "IDX_I"
}
```

Response: `{ "data": ["2026-04-03", "2026-04-10", ...], "status": "success" }`

---

## 14. Expired Options Data

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/charts/rollingoption` |

```json
{
    "exchangeSegment": "NSE_FNO",
    "interval": "5",
    "securityId": 13,
    "instrument": "OPTIDX",
    "expiryFlag": "MONTH",
    "expiryCode": 1,
    "strike": "ATM",
    "drvOptionType": "CALL",
    "requiredData": ["open", "high", "low", "close", "volume", "iv", "oi"],
    "fromDate": "2026-03-01",
    "toDate": "2026-03-30"
}
```

| Field | Values |
|-------|--------|
| `expiryFlag` | `WEEK`, `MONTH` |
| `strike` | `ATM`, `ATM+1` to `ATM+10`, `ATM-1` to `ATM-10` (Index); `ATM+1` to `ATM+3` (Stocks) |
| `requiredData` | `open`, `high`, `low`, `close`, `iv`, `volume`, `strike`, `oi`, `spot` |

> Max 30 days per API call. Data available for last 5 years.

---

## 15. Live Market Feed (WebSocket)

### Connection

```
wss://api-feed.dhan.co?version=2&token={{access_token}}&clientId={{client_id}}&authType=2
```

**Limits:** Max 5 connections, 5000 instruments/connection, 100 instruments/subscription message.

**Keep-alive:** Server pings every 10s. Disconnects after 40s inactivity.

### Subscribe Messages (JSON)

**Ticker (LTP only):**
```json
{
    "RequestCode": 15,
    "InstrumentCount": 2,
    "InstrumentList": [
        { "ExchangeSegment": "NSE_EQ", "SecurityId": "2885" },
        { "ExchangeSegment": "NSE_EQ", "SecurityId": "11536" }
    ]
}
```

**Quote (LTP + OHLC + Volume):**
```json
{ "RequestCode": 17, "InstrumentCount": 1, "InstrumentList": [{ "ExchangeSegment": "NSE_EQ", "SecurityId": "2885" }] }
```

**Full (Quote + 5-level Depth):**
```json
{ "RequestCode": 21, "InstrumentCount": 1, "InstrumentList": [{ "ExchangeSegment": "NSE_EQ", "SecurityId": "2885" }] }
```

**Unsubscribe:** Use codes `16` (Ticker), `18` (Quote), `22` (Full)
**Disconnect:** `{ "RequestCode": 12 }`

### Request Codes

| Code | Purpose |
|------|---------|
| `15` | Subscribe Ticker |
| `16` | Unsubscribe Ticker |
| `17` | Subscribe Quote |
| `18` | Unsubscribe Quote |
| `21` | Subscribe Full |
| `22` | Unsubscribe Full |
| `12` | Disconnect |

### Response Format: Binary (Little Endian)

| Packet | Response Code | Size | Key Data |
|--------|---------------|------|----------|
| Ticker | 2 | 16 bytes | LTP, Last Trade Time |
| Quote | 4 | 50 bytes | LTP, Qty, ATP, Volume, OHLC |
| OI | 5 | 12 bytes | Open Interest |
| Prev Close | 6 | 16 bytes | Previous close, Previous OI |
| Full | 8 | 162 bytes | Everything + 5-level depth |
| Disconnect | 50 | 10 bytes | Disconnect code |

### Testing WebSocket in Postman

1. Create new **WebSocket Request** in Postman
2. URL: `wss://api-feed.dhan.co?version=2&token={{access_token}}&clientId={{client_id}}&authType=2`
3. Click **Connect**
4. In the message box, paste subscribe JSON and click **Send**
5. Responses will be binary — Postman shows raw bytes

---

## 16. Full Market Depth (WebSocket)

### 20-Level Depth

```
wss://depth-api-feed.dhan.co/twentydepth?token={{access_token}}&clientId={{client_id}}&authType=2
```
Max 50 instruments. NSE only.

### 200-Level Depth

```
wss://full-depth-api.dhan.co/twohundreddepth?token={{access_token}}&clientId={{client_id}}&authType=2
```
1 instrument only. NSE only.

**Subscribe (both):**
```json
{ "RequestCode": 23, "InstrumentCount": 1, "InstrumentList": [{ "ExchangeSegment": "NSE_EQ", "SecurityId": "1333" }] }
```

---

## 17. EDIS

Required to sell holding stocks via CDSL eDIS flow.

### 17.1 Generate T-PIN

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/edis/tpin` |

Response: `202 Accepted`

### 17.2 Generate eDIS Form

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/v2/edis/form` |

```json
{
    "isin": "INE733E01010",
    "qty": 1,
    "exchange": "NSE",
    "segment": "EQ",
    "bulk": false
}
```

Response: `{ "dhanClientId": "...", "edisFormHtml": "<HTML form to render>" }`

### 17.3 eDIS Status

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/v2/edis/inquire/{isin}` |

Use `ALL` for entire portfolio: `{{base_url}}/v2/edis/inquire/ALL`

---

## 18. Enums & Error Codes

### Exchange Segments

| Enum | Code | Description |
|------|------|-------------|
| `IDX_I` | 0 | Index |
| `NSE_EQ` | 1 | NSE Equity |
| `NSE_FNO` | 2 | NSE F&O |
| `NSE_CURRENCY` | 3 | NSE Currency |
| `BSE_EQ` | 4 | BSE Equity |
| `MCX_COMM` | 5 | MCX Commodity |
| `BSE_CURRENCY` | 7 | BSE Currency |
| `BSE_FNO` | 8 | BSE F&O |

### Product Types
`CNC` (Delivery), `INTRADAY`, `MARGIN` (Carry Forward), `MTF` (Margin Trade Funding), `CO` (Cover Order), `BO` (Bracket Order)

### Order Types
`LIMIT`, `MARKET`, `STOP_LOSS`, `STOP_LOSS_MARKET`

### Transaction Types
`BUY`, `SELL`

### Validity
`DAY`, `IOC`

### Order Statuses
`TRANSIT`, `PENDING`, `CLOSED`, `TRIGGERED`, `REJECTED`, `CANCELLED`, `PART_TRADED`, `TRADED`, `EXPIRED`, `CONFIRM`

### Instrument Types
`INDEX`, `FUTIDX`, `OPTIDX`, `EQUITY`, `FUTSTK`, `OPTSTK`, `FUTCOM`, `OPTFUT`, `FUTCUR`, `OPTCUR`

### Error Codes

| Code | Type | Description |
|------|------|-------------|
| `DH-901` | Auth | Client ID or access token invalid/expired |
| `DH-902` | Access | Subscription or permission issues |
| `DH-903` | Account | Account config problems |
| `DH-904` | Rate Limit | Too many requests |
| `DH-905` | Input | Missing/invalid parameters |
| `DH-906` | Order | Incorrect order request |
| `DH-907` | Data | Data retrieval failure |
| `DH-908` | Server | Internal error |
| `DH-909` | Network | Backend communication failure |
| `DH-910` | Other | Miscellaneous |

### Data API Error Codes
`800` (Server Error), `804` (Instrument limit exceeded), `805` (Too many requests/connections), `806` (Data APIs not subscribed), `807` (Token expired), `808` (Auth failed), `809` (Invalid token), `810` (Invalid client ID), `811` (Invalid expiry), `812` (Invalid date format), `813` (Invalid security ID), `814` (Invalid request)

### Error Response Format
```json
{
    "errorType": "DH-905",
    "errorCode": "DH-905",
    "errorMessage": "Missing required field: securityId"
}
```

---

## 19. Rate Limits

| Category | Per Second | Per Minute | Per Hour | Per Day |
|----------|-----------|-----------|---------|---------|
| Order APIs | 10 | 250 | 1000 | 7000 |
| Data APIs | 5 | — | — | 100,000 |
| Quote APIs (REST) | 1 | Unlimited | Unlimited | Unlimited |
| Non-Trading APIs | 20 | Unlimited | Unlimited | Unlimited |
| Option Chain | 1 per 3s per underlying | — | — | — |

- Order modifications: max **25 per order**
- WebSocket: max **5 connections**, **5000 instruments/connection**
- Quote REST: max **1000 instruments per request**

---

## Quick Endpoint Summary (All 50+ Endpoints)

### Orders (9)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 1 | POST | `/v2/orders` | Place order |
| 2 | PUT | `/v2/orders/{id}` | Modify order |
| 3 | DELETE | `/v2/orders/{id}` | Cancel order |
| 4 | POST | `/v2/orders/slicing` | Slice order |
| 5 | GET | `/v2/orders` | Order book |
| 6 | GET | `/v2/orders/{id}` | Order by ID |
| 7 | GET | `/v2/orders/external/{corrId}` | Order by correlation ID |
| 8 | GET | `/v2/trades` | Trade book |
| 9 | GET | `/v2/trades/{orderId}` | Trades for order |

### Super Orders (4)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 10 | POST | `/v2/super/orders` | Place super order |
| 11 | PUT | `/v2/super/orders/{id}` | Modify super order |
| 12 | DELETE | `/v2/super/orders/{id}/{leg}` | Cancel super order leg |
| 13 | GET | `/v2/super/orders` | Get all super orders |

### Forever Orders (4)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 14 | POST | `/v2/forever/orders` | Create forever order |
| 15 | PUT | `/v2/forever/orders/{id}` | Modify forever order |
| 16 | DELETE | `/v2/forever/orders/{id}` | Delete forever order |
| 17 | GET | `/v2/forever/all` | Get all forever orders |

### Conditional Triggers (5)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 18 | POST | `/v2/alerts/orders` | Create trigger |
| 19 | PUT | `/v2/alerts/orders/{alertId}` | Modify trigger |
| 20 | DELETE | `/v2/alerts/orders/{alertId}` | Cancel trigger |
| 21 | GET | `/v2/alerts/orders/{alertId}` | Get trigger by ID |
| 22 | GET | `/v2/alerts/orders` | Get all triggers |

### Portfolio (4)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 23 | GET | `/v2/holdings` | Get holdings |
| 24 | GET | `/v2/positions` | Get positions |
| 25 | POST | `/v2/positions/convert` | Convert position |
| 26 | DELETE | `/v2/positions` | Exit all positions |

### Funds (3)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 27 | POST | `/v2/margincalculator` | Single margin calc |
| 28 | POST | `/v2/margincalculator/multi` | Multi margin calc |
| 29 | GET | `/v2/fundlimit` | Fund limit |

### Trader's Control (6)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 30 | POST | `/v2/killswitch?killSwitchStatus=ACTIVATE` | Activate kill switch |
| 31 | POST | `/v2/killswitch?killSwitchStatus=DEACTIVATE` | Deactivate kill switch |
| 32 | GET | `/v2/killswitch` | Kill switch status |
| 33 | POST | `/v2/pnlExit` | Set P&L exit |
| 34 | DELETE | `/v2/pnlExit` | Stop P&L exit |
| 35 | GET | `/v2/pnlExit` | P&L exit status |

### Statements (2)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 36 | GET | `/v2/ledger?from-date=&to-date=` | Ledger report |
| 37 | GET | `/v2/trades/{from}/{to}/{page}` | Trade history |

### Market Data REST (5)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 38 | POST | `/v2/marketfeed/ltp` | LTP |
| 39 | POST | `/v2/marketfeed/ohlc` | OHLC |
| 40 | POST | `/v2/marketfeed/quote` | Full quote + depth |
| 41 | POST | `/v2/charts/historical` | Daily candles |
| 42 | POST | `/v2/charts/intraday` | Intraday candles |

### Options (3)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 43 | POST | `/v2/optionchain` | Option chain |
| 44 | POST | `/v2/optionchain/expirylist` | Expiry list |
| 45 | POST | `/v2/charts/rollingoption` | Expired options data |

### EDIS (3)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 46 | GET | `/v2/edis/tpin` | Generate T-PIN |
| 47 | POST | `/v2/edis/form` | Generate eDIS form |
| 48 | GET | `/v2/edis/inquire/{isin}` | eDIS status |

### Auth & Config (5)
| # | Method | URL | Description |
|---|--------|-----|-------------|
| 49 | POST | `auth.dhan.co/app/generateAccessToken` | Token via TOTP |
| 50 | GET | `/v2/RenewToken` | Renew token |
| 51 | GET | `/v2/profile` | Profile info |
| 52 | POST | `/v2/ip/setIP` | Set static IP |
| 53 | GET | `/v2/ip/getIP` | Get current IP |

### WebSocket (3 connections)
| # | URL | Description |
|---|-----|-------------|
| 54 | `wss://api-feed.dhan.co?version=2&token=...` | Live market feed |
| 55 | `wss://depth-api-feed.dhan.co/twentydepth?token=...` | 20-level depth |
| 56 | `wss://full-depth-api.dhan.co/twohundreddepth?token=...` | 200-level depth |

---

## Postman Testing Checklist

### Phase 1 — Auth & Read-Only (Safe, no orders)
- [ ] Generate/paste access token
- [ ] `GET /v2/profile` — verify token works
- [ ] `GET /v2/fundlimit` — check balance
- [ ] `GET /v2/holdings` — see holdings
- [ ] `GET /v2/positions` — see positions
- [ ] `GET /v2/orders` — see order book
- [ ] `GET /v2/trades` — see trade book
- [ ] `GET /v2/killswitch` — check status

### Phase 2 — Market Data (Read-only)
- [ ] `POST /v2/marketfeed/ltp` — get live prices
- [ ] `POST /v2/marketfeed/ohlc` — get OHLC
- [ ] `POST /v2/marketfeed/quote` — get full quote
- [ ] `POST /v2/charts/historical` — daily candles
- [ ] `POST /v2/charts/intraday` — intraday candles
- [ ] `POST /v2/optionchain/expirylist` — get expiries
- [ ] `POST /v2/optionchain` — get option chain

### Phase 3 — Orders (Use Sandbox first!)
- [ ] Switch `base_url` to `https://sandbox.dhan.co`
- [ ] `POST /v2/orders` — place test order
- [ ] `GET /v2/orders/{id}` — verify order
- [ ] `PUT /v2/orders/{id}` — modify order
- [ ] `DELETE /v2/orders/{id}` — cancel order
- [ ] `POST /v2/margincalculator` — check margin

### Phase 4 — Advanced Orders
- [ ] `POST /v2/super/orders` — super order
- [ ] `POST /v2/forever/orders` — GTT order
- [ ] `POST /v2/alerts/orders` — conditional trigger

### Phase 5 — WebSocket
- [ ] Connect to `wss://api-feed.dhan.co?version=2&...`
- [ ] Subscribe ticker (code 15)
- [ ] Subscribe quote (code 17)
- [ ] Subscribe full (code 21)

---

## Common Security IDs for Testing

| Stock | NSE Security ID |
|-------|----------------|
| RELIANCE | 2885 |
| TCS | 11536 |
| HDFCBANK | 1333 |
| INFY | 1594 |
| SBIN | 3045 |
| TATAMOTORS | 3456 |
| BAJFINANCE | 317 |
| ITC | 1660 |
| NIFTY 50 (Index) | 13 |
| BANK NIFTY (Index) | 25 |

> Full instrument list: Download from Dhan's CSV at https://images.dhan.co/api-data/api-scrip-master.csv
