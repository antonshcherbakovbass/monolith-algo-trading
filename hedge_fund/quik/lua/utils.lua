-- utils.lua - Helper functions for QUIK LUA integration
-- JSON encoding/decoding, formatting, debugging utilities

local utils = {}

-- ---------------------------------------------------------------------------
-- JSON encoder
-- ---------------------------------------------------------------------------

local escape_char_map = {
    ["\\"] = "\\\\", ["\""] = "\\\"", ["\b"] = "\\b",
    ["\f"] = "\\f",  ["\n"] = "\\n",  ["\r"] = "\\r",
    ["\t"] = "\\t",
}

local function escape_char(c)
    return escape_char_map[c] or string.format("\\u%04x", c:byte())
end

local function encode_string(val)
    return '"' .. val:gsub('[%z\1-\31\\"]', escape_char) .. '"'
end

local function encode_number(val)
    if val ~= val then return '"NaN"' end
    if val <= -math.huge then return '"-Infinity"' end
    if val >= math.huge then return '"Infinity"' end
    return string.format("%.14g", val)
end

local encode_value  -- forward declaration

local function encode_table(val, visited)
    if visited[val] then error("circular reference in table") end
    visited[val] = true

    -- detect array vs object: array if keys are 1..n
    local n = #val
    local is_array = true
    if n == 0 then
        for _ in pairs(val) do is_array = false; break end
    else
        local count = 0
        for _ in pairs(val) do count = count + 1 end
        if count ~= n then is_array = false end
    end

    local parts = {}
    if is_array then
        for i = 1, n do
            parts[i] = encode_value(val[i], visited)
        end
        visited[val] = nil
        return "[" .. table.concat(parts, ",") .. "]"
    else
        local idx = 0
        for k, v in pairs(val) do
            idx = idx + 1
            parts[idx] = encode_string(tostring(k)) .. ":" .. encode_value(v, visited)
        end
        visited[val] = nil
        return "{" .. table.concat(parts, ",") .. "}"
    end
end

encode_value = function(val, visited)
    local t = type(val)
    if t == "string"  then return encode_string(val) end
    if t == "number"  then return encode_number(val) end
    if t == "boolean" then return val and "true" or "false" end
    if t == "nil"     then return "null" end
    if t == "table"   then return encode_table(val, visited) end
    error("unsupported type: " .. t)
end

function utils.json_encode(val)
    local ok, result = pcall(encode_value, val, {})
    if ok then return result end
    return nil, result
end

-- ---------------------------------------------------------------------------
-- JSON decoder
-- ---------------------------------------------------------------------------

local function skip_ws(str, pos)
    return str:match("^%s*()", pos)
end

local decode_value  -- forward declaration

local escape_chars = {
    ["b"] = "\b", ["f"] = "\f", ["n"] = "\n",
    ["r"] = "\r", ["t"] = "\t", ["\\"] = "\\", ['"'] = '"', ["/"] = "/",
}

local function decode_string(str, pos)
    pos = pos + 1  -- skip opening quote
    local parts = {}
    while true do
        local c = str:sub(pos, pos)
        if c == "" then error("unterminated string") end
        if c == '"' then return table.concat(parts), pos + 1 end
        if c == "\\" then
            pos = pos + 1
            local esc = str:sub(pos, pos)
            if esc == "u" then
                local hex = str:sub(pos + 1, pos + 4)
                local code = tonumber(hex, 16)
                if not code then error("invalid unicode escape") end
                parts[#parts + 1] = string.char(code % 256)
                pos = pos + 5
            else
                parts[#parts + 1] = escape_chars[esc] or esc
                pos = pos + 1
            end
        else
            parts[#parts + 1] = c
            pos = pos + 1
        end
    end
end

local function decode_number(str, pos)
    local num_str = str:match("^-?%d+%.?%d*[eE]?[+-]?%d*", pos)
    if not num_str then error("invalid number at position " .. pos) end
    return tonumber(num_str), pos + #num_str
end

local function decode_array(str, pos)
    local arr = {}
    pos = skip_ws(str, pos + 1)  -- skip '['
    if str:sub(pos, pos) == "]" then return arr, pos + 1 end
    while true do
        local val
        val, pos = decode_value(str, pos)
        arr[#arr + 1] = val
        pos = skip_ws(str, pos)
        local c = str:sub(pos, pos)
        if c == "]" then return arr, pos + 1 end
        if c ~= "," then error("expected ',' or ']'") end
        pos = skip_ws(str, pos + 1)
    end
end

local function decode_object(str, pos)
    local obj = {}
    pos = skip_ws(str, pos + 1)  -- skip '{'
    if str:sub(pos, pos) == "}" then return obj, pos + 1 end
    while true do
        if str:sub(pos, pos) ~= '"' then error("expected string key") end
        local key
        key, pos = decode_string(str, pos)
        pos = skip_ws(str, pos)
        if str:sub(pos, pos) ~= ":" then error("expected ':'") end
        pos = skip_ws(str, pos + 1)
        local val
        val, pos = decode_value(str, pos)
        obj[key] = val
        pos = skip_ws(str, pos)
        local c = str:sub(pos, pos)
        if c == "}" then return obj, pos + 1 end
        if c ~= "," then error("expected ',' or '}'") end
        pos = skip_ws(str, pos + 1)
    end
end

decode_value = function(str, pos)
    pos = skip_ws(str, pos)
    local c = str:sub(pos, pos)
    if c == '"' then return decode_string(str, pos) end
    if c == "{" then return decode_object(str, pos) end
    if c == "[" then return decode_array(str, pos) end
    if c == "t" then
        if str:sub(pos, pos + 3) == "true" then return true, pos + 4 end
        error("invalid literal")
    end
    if c == "f" then
        if str:sub(pos, pos + 4) == "false" then return false, pos + 5 end
        error("invalid literal")
    end
    if c == "n" then
        if str:sub(pos, pos + 3) == "null" then return nil, pos + 4 end
        error("invalid literal")
    end
    if c == "-" or (c >= "0" and c <= "9") then
        return decode_number(str, pos)
    end
    error("unexpected character '" .. c .. "' at position " .. pos)
end

function utils.json_decode(str)
    if type(str) ~= "string" or #str == 0 then
        return nil, "empty or non-string input"
    end
    local ok, result, _ = pcall(decode_value, str, 1)
    if ok then return result end
    return nil, result
end

-- ---------------------------------------------------------------------------
-- Formatting helpers
-- ---------------------------------------------------------------------------

function utils.format_price(price, decimals)
    if price == nil then return "N/A" end
    decimals = decimals or 2
    return string.format("%." .. decimals .. "f", tonumber(price) or 0)
end

function utils.get_class_info(class_code)
    if not getClassInfo then return nil, "getClassInfo not available" end
    local info = getClassInfo(class_code)
    if not info then return nil, "class not found: " .. tostring(class_code) end
    return {
        code      = info.code,
        name      = info.name,
        npars     = info.npars,
        nsecs     = info.nsecs,
        firmid    = info.firmid,
    }
end

function utils.timestamp_to_string(ts)
    if type(ts) == "table" then
        return string.format("%04d-%02d-%02d %02d:%02d:%02d",
            ts.year or 0, ts.month or 0, ts.day or 0,
            ts.hour or 0, ts.min or 0, ts.sec or 0)
    end
    if type(ts) == "number" then
        local d = os.date("*t", ts)
        return string.format("%04d-%02d-%02d %02d:%02d:%02d",
            d.year, d.month, d.day, d.hour, d.min, d.sec)
    end
    return tostring(ts)
end

function utils.table_to_string(t, indent)
    if type(t) ~= "table" then return tostring(t) end
    indent = indent or 0
    local pad = string.rep("  ", indent)
    local parts = {}
    parts[#parts + 1] = "{"
    for k, v in pairs(t) do
        local key_str = tostring(k)
        local val_str
        if type(v) == "table" then
            val_str = utils.table_to_string(v, indent + 1)
        elseif type(v) == "string" then
            val_str = '"' .. v .. '"'
        else
            val_str = tostring(v)
        end
        parts[#parts + 1] = pad .. "  " .. key_str .. " = " .. val_str
    end
    parts[#parts + 1] = pad .. "}"
    return table.concat(parts, "\n")
end

return utils
