-- main.lua - QUIK 12.8.4.9 TCP socket server for Python integration
-- Starts a JSON-over-TCP server, handles commands, pushes callbacks

local socket = require("socket")  -- QUIK built-in socket library
local utils  = require("utils")

-- ---------------------------------------------------------------------------
-- Configuration
-- ---------------------------------------------------------------------------

local CONFIG = {
    port              = 34130,
    max_requests_sec  = 50,
    heartbeat_interval = 5,
    recv_timeout       = 0.001,    -- non-blocking receive timeout (seconds)
    accept_timeout     = 0.001,
    max_send_queue     = 10000,
    log_level          = "INFO",   -- DEBUG, INFO, WARN, ERROR
}

-- ---------------------------------------------------------------------------
-- State
-- ---------------------------------------------------------------------------

local server_socket   = nil
local client_socket   = nil
local is_running      = false
local subscriptions   = {}         -- ["CLASS:TICKER"] = true
local request_count   = 0
local request_window  = 0          -- os.clock() of current window
local send_queue      = {}         -- outbound messages queued for client
local recv_buffer     = ""         -- partial receive buffer

-- ---------------------------------------------------------------------------
-- Logging
-- ---------------------------------------------------------------------------

local LOG_LEVELS = { DEBUG = 1, INFO = 2, WARN = 3, ERROR = 4 }

local function log(level, msg)
    if LOG_LEVELS[level] and LOG_LEVELS[level] >= LOG_LEVELS[CONFIG.log_level] then
        local text = os.date("%H:%M:%S") .. " [" .. level .. "] " .. msg
        if message then
            message(text)
        end
    end
end

-- ---------------------------------------------------------------------------
-- Send / receive helpers
-- ---------------------------------------------------------------------------

local function enqueue_message(msg_table)
    local encoded, err = utils.json_encode(msg_table)
    if not encoded then
        log("ERROR", "json_encode failed: " .. tostring(err))
        return
    end
    if #send_queue >= CONFIG.max_send_queue then
        table.remove(send_queue, 1)
    end
    send_queue[#send_queue + 1] = encoded .. "\n"
end

local function send_response(id, result, error_msg)
    local resp = { type = "response", id = id }
    if error_msg then
        resp.error = error_msg
    else
        resp.result = result
    end
    enqueue_message(resp)
end

local function push_event(event_type, data)
    enqueue_message({ type = "event", event = event_type, data = data })
end

local function flush_send_queue()
    if not client_socket or #send_queue == 0 then return end
    local batch = table.concat(send_queue)
    send_queue = {}
    local bytes, err = client_socket:send(batch)
    if not bytes then
        log("WARN", "send failed: " .. tostring(err))
        client_socket:close()
        client_socket = nil
    end
end

-- ---------------------------------------------------------------------------
-- Rate limiting
-- ---------------------------------------------------------------------------

local function rate_limit_ok()
    local now = os.clock()
    if now - request_window >= 1.0 then
        request_window = now
        request_count = 0
    end
    if request_count >= CONFIG.max_requests_sec then
        return false
    end
    request_count = request_count + 1
    return true
end

-- ---------------------------------------------------------------------------
-- Message handlers
-- ---------------------------------------------------------------------------

local handlers = {}

function handlers.subscribe(params)
    local class_code = params.class_code
    local sec_code   = params.sec_code
    if not class_code or not sec_code then
        return nil, "class_code and sec_code required"
    end
    local key = class_code .. ":" .. sec_code
    subscriptions[key] = true
    if Subscribe_Level_II_Quotes then
        Subscribe_Level_II_Quotes(class_code, sec_code)
    end
    log("INFO", "subscribed: " .. key)
    return { subscribed = key }
end

function handlers.unsubscribe(params)
    local class_code = params.class_code
    local sec_code   = params.sec_code
    if not class_code or not sec_code then
        return nil, "class_code and sec_code required"
    end
    local key = class_code .. ":" .. sec_code
    subscriptions[key] = nil
    if Unsubscribe_Level_II_Quotes then
        Unsubscribe_Level_II_Quotes(class_code, sec_code)
    end
    log("INFO", "unsubscribed: " .. key)
    return { unsubscribed = key }
end

function handlers.get_quote(params)
    local class_code = params.class_code
    local sec_code   = params.sec_code
    if not class_code or not sec_code then
        return nil, "class_code and sec_code required"
    end
    if not getParamEx then
        return nil, "getParamEx not available"
    end
    local function p(name)
        local r = getParamEx(class_code, sec_code, name)
        if r then return tonumber(r.param_value) end
        return nil
    end
    return {
        class_code = class_code,
        sec_code   = sec_code,
        last       = p("LAST"),
        bid        = p("BID"),
        ask        = p("OFFER"),
        volume     = p("VOLTODAY"),
        open       = p("OPEN"),
        high       = p("HIGH"),
        low        = p("LOW"),
        close      = p("PREVLEGALCLOSEPR"),
        change     = p("CHANGE"),
        change_pct = p("CHANGEPRCNT"),
        num_trades = p("NUMTRADES"),
        value      = p("VALTODAY"),
        waprice    = p("WAPRICE"),
        time       = p("TRADETIME"),
    }
end

function handlers.get_orderbook(params)
    local class_code = params.class_code
    local sec_code   = params.sec_code
    if not class_code or not sec_code then
        return nil, "class_code and sec_code required"
    end
    if not getQuoteLevel2 then
        return nil, "getQuoteLevel2 not available"
    end
    local ql2 = getQuoteLevel2(class_code, sec_code)
    if not ql2 then
        return nil, "no orderbook data"
    end
    local bids, asks = {}, {}
    if ql2.bid and ql2.bid_count then
        for i = 1, tonumber(ql2.bid_count) or 0 do
            local entry = ql2.bid[i]
            if entry then
                bids[#bids + 1] = {
                    price    = tonumber(entry.price),
                    quantity = tonumber(entry.quantity),
                }
            end
        end
    end
    if ql2.offer and ql2.offer_count then
        for i = 1, tonumber(ql2.offer_count) or 0 do
            local entry = ql2.offer[i]
            if entry then
                asks[#asks + 1] = {
                    price    = tonumber(entry.price),
                    quantity = tonumber(entry.quantity),
                }
            end
        end
    end
    return {
        class_code = class_code,
        sec_code   = sec_code,
        bids       = bids,
        asks       = asks,
        bid_count  = tonumber(ql2.bid_count) or 0,
        ask_count  = tonumber(ql2.offer_count) or 0,
    }
end

function handlers.get_candles(params)
    local class_code = params.class_code
    local sec_code   = params.sec_code
    local interval   = params.interval or 1  -- INTERVAL_M1 by default
    local count      = params.count or 100
    if not class_code or not sec_code then
        return nil, "class_code and sec_code required"
    end
    if not CreateDataSource then
        return nil, "CreateDataSource not available"
    end
    local ds, err = CreateDataSource(class_code, sec_code, interval)
    if not ds then
        return nil, "CreateDataSource failed: " .. tostring(err)
    end
    ds:SetEmptyCallback()
    local total = ds:Size()
    local start = math.max(1, total - count + 1)
    local candles = {}
    for i = start, total do
        local t = ds:T(i)
        candles[#candles + 1] = {
            open   = ds:O(i),
            high   = ds:H(i),
            low    = ds:L(i),
            close  = ds:C(i),
            volume = ds:V(i),
            time   = utils.timestamp_to_string(t),
        }
    end
    ds:Close()
    return { class_code = class_code, sec_code = sec_code, interval = interval, candles = candles }
end

function handlers.send_order(params)
    if not sendTransaction then
        return nil, "sendTransaction not available"
    end
    local required = { "TRANS_ID", "ACTION", "CLASSCODE", "SECCODE", "OPERATION", "QUANTITY" }
    for _, field in ipairs(required) do
        if not params[field] then
            return nil, "missing required field: " .. field
        end
    end
    local trans = {}
    local allowed_fields = {
        "TRANS_ID", "ACTION", "CLASSCODE", "SECCODE", "TYPE", "OPERATION",
        "QUANTITY", "PRICE", "STOP_STOPPRICE", "STOP_PROFITPRICE",
        "ACCOUNT", "CLIENT_CODE", "COMMENT", "FIRMID", "PARTNER",
        "EXECUTION_CONDITION", "EXPIRY_DATE",
    }
    for _, field in ipairs(allowed_fields) do
        if params[field] ~= nil then
            trans[field] = tostring(params[field])
        end
    end
    local result = sendTransaction(trans)
    if result and result ~= "" then
        return nil, "sendTransaction error: " .. result
    end
    log("INFO", "order sent: " .. tostring(params.TRANS_ID))
    return { trans_id = params.TRANS_ID, status = "sent" }
end

function handlers.cancel_order(params)
    if not sendTransaction then
        return nil, "sendTransaction not available"
    end
    if not params.order_id or not params.class_code or not params.sec_code then
        return nil, "order_id, class_code, sec_code required"
    end
    local trans = {
        TRANS_ID  = tostring(params.trans_id or os.time()),
        ACTION    = "KILL_ORDER",
        CLASSCODE = params.class_code,
        SECCODE   = params.sec_code,
        ORDER_KEY = tostring(params.order_id),
    }
    if params.account then trans.ACCOUNT = params.account end
    local result = sendTransaction(trans)
    if result and result ~= "" then
        return nil, "cancel error: " .. result
    end
    log("INFO", "cancel sent for order: " .. tostring(params.order_id))
    return { order_id = params.order_id, status = "cancel_sent" }
end

function handlers.get_positions(params)
    if not getFuturesHolding and not getDepoEx then
        return nil, "position functions not available"
    end
    local account   = params.account or ""
    local firmid    = params.firmid or ""
    local positions = {}

    if getNumberOf and getItem then
        local n = getNumberOf("depo_limits")
        for i = 0, n - 1 do
            local item = getItem("depo_limits", i)
            if item and (account == "" or item.trdaccid == account) then
                local current = tonumber(item.currentbal) or 0
                if current ~= 0 then
                    positions[#positions + 1] = {
                        sec_code   = item.sec_code,
                        account    = item.trdaccid,
                        current    = current,
                        locked_buy = tonumber(item.lockedbuy) or 0,
                        locked_sell = tonumber(item.lockedsell) or 0,
                        awg_price  = tonumber(item.awg_position_price) or 0,
                    }
                end
            end
        end
    end

    if getNumberOf then
        local n = getNumberOf("futures_client_holding")
        for i = 0, n - 1 do
            local item = getItem("futures_client_holding", i)
            if item and (account == "" or item.trdaccid == account) then
                local pos = tonumber(item.totalnet) or 0
                if pos ~= 0 then
                    positions[#positions + 1] = {
                        sec_code   = item.sec_code,
                        account    = item.trdaccid,
                        net        = pos,
                        buy_qty    = tonumber(item.todaybuy) or 0,
                        sell_qty   = tonumber(item.todaysell) or 0,
                        awg_price  = tonumber(item.avrposnprice) or 0,
                        varmargin  = tonumber(item.varmargin) or 0,
                        type       = "futures",
                    }
                end
            end
        end
    end

    return { positions = positions }
end

function handlers.get_money(params)
    if not getMoney and not getMoneyEx then
        return nil, "getMoney not available"
    end
    local firmid    = params.firmid or ""
    local client    = params.client_code or ""
    local tag       = params.tag or "EQTV"
    local limit_kind = params.limit_kind or 0

    local result = {}
    if getMoneyEx then
        local m = getMoneyEx(firmid, client, tag, "SUR", limit_kind)
        if m then
            result.balance       = tonumber(m.currentbal) or 0
            result.available     = tonumber(m.currentlimit) or 0
            result.locked        = tonumber(m.locked) or 0
            result.comission     = tonumber(m.comission) or 0
            result.limit_kind    = limit_kind
        end
    elseif getMoney then
        local m = getMoney(firmid, client, tag, "SUR")
        if m then
            result.balance       = tonumber(m.currentbal) or 0
            result.available     = tonumber(m.currentlimit) or 0
            result.locked        = tonumber(m.locked) or 0
        end
    end

    if getNumberOf then
        local n = getNumberOf("futures_client_limits")
        for i = 0, n - 1 do
            local item = getItem("futures_client_limits", i)
            if item and (firmid == "" or item.firmid == firmid) then
                result.fut_limit     = tonumber(item.cbplimit) or 0
                result.fut_available = tonumber(item.cbplused) or 0
                result.fut_varmargin = tonumber(item.varmargin) or 0
                result.fut_go        = tonumber(item.ts_comission) or 0
                break
            end
        end
    end

    return result
end

function handlers.get_trades(params)
    local account = params.account or ""
    local count   = params.count or 100
    if not getNumberOf or not getItem then
        return nil, "table functions not available"
    end
    local trades = {}
    local n = getNumberOf("trades")
    local start = math.max(0, n - count)
    for i = start, n - 1 do
        local item = getItem("trades", i)
        if item and (account == "" or item.account == account) then
            trades[#trades + 1] = {
                trade_num  = tostring(item.trade_num),
                order_num  = tostring(item.order_num),
                class_code = item.class_code,
                sec_code   = item.sec_code,
                price      = tonumber(item.price) or 0,
                qty        = tonumber(item.qty) or 0,
                value      = tonumber(item.value) or 0,
                side       = tonumber(item.flags) and (bit.band(item.flags, 0x4) ~= 0 and "sell" or "buy") or "unknown",
                time       = item.datetime and utils.timestamp_to_string(item.datetime) or "",
                account    = item.account,
            }
        end
    end
    return { trades = trades }
end

function handlers.get_info(_)
    local result = {
        connected   = isConnected and isConnected() == 1 or false,
        server_time = getInfoParam and getInfoParam("SERVERTIME") or "",
        version     = getInfoParam and getInfoParam("VERSION") or "",
        trader      = getInfoParam and getInfoParam("TRADERACCOUNT") or "",
        user        = getInfoParam and getInfoParam("USER") or "",
        org         = getInfoParam and getInfoParam("ORG") or "",
        server      = getInfoParam and getInfoParam("SERVER") or "",
        connection  = getInfoParam and getInfoParam("CONNECTION") or "",
        latency     = getInfoParam and getInfoParam("LASTRECORDTIME") or "",
    }
    return result
end

function handlers.heartbeat(_)
    return { pong = true, time = os.time() }
end

-- ---------------------------------------------------------------------------
-- Process incoming request
-- ---------------------------------------------------------------------------

local function process_request(request_str)
    local msg, err = utils.json_decode(request_str)
    if not msg then
        log("ERROR", "decode failed: " .. tostring(err))
        return
    end

    local id     = msg.id
    local method = msg.method
    local params = msg.params or {}

    if not method then
        send_response(id, nil, "missing method")
        return
    end

    if not rate_limit_ok() then
        send_response(id, nil, "rate limit exceeded")
        return
    end

    local handler = handlers[method]
    if not handler then
        send_response(id, nil, "unknown method: " .. tostring(method))
        return
    end

    local ok, result_or_err, error_msg = pcall(handler, params)
    if not ok then
        send_response(id, nil, "handler error: " .. tostring(result_or_err))
    elseif error_msg then
        send_response(id, nil, error_msg)
    else
        send_response(id, result_or_err)
    end
end

-- ---------------------------------------------------------------------------
-- QUIK callbacks
-- ---------------------------------------------------------------------------

function OnQuote(class_code, sec_code)
    local key = class_code .. ":" .. sec_code
    if not subscriptions[key] then return end
    local ok, result = pcall(handlers.get_quote, { class_code = class_code, sec_code = sec_code })
    if ok and result then
        push_event("quote", result)
    end
end

function OnTrade(trade)
    if not trade then return end
    push_event("trade", {
        trade_num  = tostring(trade.trade_num),
        order_num  = tostring(trade.order_num),
        class_code = trade.class_code,
        sec_code   = trade.sec_code,
        price      = tonumber(trade.price) or 0,
        qty        = tonumber(trade.qty) or 0,
        side       = tonumber(trade.flags) and (bit.band(trade.flags, 0x4) ~= 0 and "sell" or "buy") or "unknown",
        time       = trade.datetime and utils.timestamp_to_string(trade.datetime) or "",
        account    = trade.account,
    })
end

function OnOrder(order)
    if not order then return end
    local flags = tonumber(order.flags) or 0
    local status = "active"
    if bit.band(flags, 0x1) ~= 0 then status = "cancelled" end
    if bit.band(flags, 0x2) ~= 0 then status = "filled" end
    push_event("order", {
        order_num  = tostring(order.order_num),
        class_code = order.class_code,
        sec_code   = order.sec_code,
        price      = tonumber(order.price) or 0,
        qty        = tonumber(order.qty) or 0,
        balance    = tonumber(order.balance) or 0,
        side       = bit.band(flags, 0x4) ~= 0 and "sell" or "buy",
        status     = status,
        trans_id   = tonumber(order.trans_id) or 0,
        account    = order.account,
    })
end

function OnTransReply(reply)
    if not reply then return end
    push_event("trans_reply", {
        trans_id    = tonumber(reply.trans_id) or 0,
        status      = tonumber(reply.status) or 0,
        result_msg  = reply.result_msg or "",
        order_num   = tostring(reply.order_num or ""),
        balance     = tonumber(reply.balance) or 0,
    })
end

-- ---------------------------------------------------------------------------
-- TCP server loop (runs in main QUIK callback thread)
-- ---------------------------------------------------------------------------

local function accept_client()
    if client_socket then return end
    server_socket:settimeout(CONFIG.accept_timeout)
    local client, err = server_socket:accept()
    if client then
        client:settimeout(CONFIG.recv_timeout)
        client:setoption("tcp-nodelay", true)
        client_socket = client
        recv_buffer = ""
        send_queue = {}
        log("INFO", "client connected from " .. tostring(client:getpeername()))
    end
end

local function receive_data()
    if not client_socket then return end
    local data, err, partial = client_socket:receive("*l")
    if data then
        recv_buffer = recv_buffer .. data
        -- process complete lines
        while true do
            local nl = recv_buffer:find("\n")
            if not nl then
                -- single line without newline = complete message (TCP line mode)
                if #recv_buffer > 0 then
                    local line = recv_buffer
                    recv_buffer = ""
                    process_request(line)
                end
                break
            end
            local line = recv_buffer:sub(1, nl - 1)
            recv_buffer = recv_buffer:sub(nl + 1)
            if #line > 0 then
                process_request(line)
            end
        end
    elseif partial and #partial > 0 then
        recv_buffer = recv_buffer .. partial
    elseif err == "closed" then
        log("WARN", "client disconnected")
        client_socket:close()
        client_socket = nil
    end
end

-- ---------------------------------------------------------------------------
-- Main entry point
-- ---------------------------------------------------------------------------

function OnInit(script_path)
    log("INFO", "initializing QUIK bridge on port " .. CONFIG.port)
end

function OnStop(signal)
    is_running = false
    log("INFO", "stopping QUIK bridge (signal=" .. tostring(signal) .. ")")
    if client_socket then pcall(function() client_socket:close() end) end
    if server_socket then pcall(function() server_socket:close() end) end
    return 1000
end

function main()
    is_running = true

    server_socket = socket.tcp()
    server_socket:setoption("reuseaddr", true)
    local ok, err = server_socket:bind("127.0.0.1", CONFIG.port)
    if not ok then
        log("ERROR", "bind failed: " .. tostring(err))
        return
    end
    server_socket:listen(1)
    server_socket:settimeout(CONFIG.accept_timeout)
    log("INFO", "TCP server listening on 127.0.0.1:" .. CONFIG.port)

    while is_running do
        if not client_socket then
            accept_client()
        else
            receive_data()
            flush_send_queue()
        end
        sleep(1)  -- QUIK sleep: 1ms, yields to callbacks
    end
end
