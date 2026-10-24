script_name = "按目标时间平移字幕"
script_description = "把所选字幕、当前字幕及之后或全部字幕平移，使范围内第一行从指定时间开始"
script_author = "Codex"
script_version = "1.0.0"

local SCOPE_SELECTED = "所选字幕"
local SCOPE_FROM_CURRENT = "第一条所选字幕及之后"
local SCOPE_ALL = "所有字幕"

local function trim(text)
    return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function fraction_to_ms(fraction)
    if not fraction or fraction == "" then
        return 0
    end

    if #fraction == 1 then
        return tonumber(fraction) * 100
    elseif #fraction == 2 then
        return tonumber(fraction) * 10
    end

    return tonumber(fraction:sub(1, 3))
end

-- 支持 H:MM:SS.cc、H:MM:SS.mmm、MM:SS.cc 以及纯毫秒数。
local function parse_time(text)
    text = trim(text)

    if text:match("^%d+$") then
        return tonumber(text)
    end

    local hours, minutes, seconds, fraction =
        text:match("^(%d+):(%d%d?):(%d%d?)[%.,](%d+)$")
    if not hours then
        hours, minutes, seconds = text:match("^(%d+):(%d%d?):(%d%d?)$")
    end

    if not hours then
        minutes, seconds, fraction = text:match("^(%d+):(%d%d?)[%.,](%d+)$")
        hours = "0"
    end
    if not minutes then
        minutes, seconds = text:match("^(%d+):(%d%d?)$")
        hours = "0"
    end

    if not hours or not minutes or not seconds then
        return nil
    end

    hours = tonumber(hours)
    minutes = tonumber(minutes)
    seconds = tonumber(seconds)
    if minutes >= 60 or seconds >= 60 then
        return nil
    end

    return ((hours * 60 + minutes) * 60 + seconds) * 1000
        + fraction_to_ms(fraction)
end

local function format_time(milliseconds)
    milliseconds = math.max(0, math.floor(milliseconds + 0.5))
    local hours = math.floor(milliseconds / 3600000)
    local minutes = math.floor(milliseconds / 60000) % 60
    local seconds = math.floor(milliseconds / 1000) % 60
    local remainder = milliseconds % 1000
    return string.format("%d:%02d:%02d.%03d", hours, minutes, seconds, remainder)
end

local function show_message(message)
    aegisub.dialog.display({
        {class = "label", label = message, x = 0, y = 0, width = 1, height = 1}
    })
end

local function collect_targets(subtitles, selected_lines, anchor_index, scope)
    local targets = {}

    if scope == SCOPE_SELECTED then
        for _, index in ipairs(selected_lines) do
            if subtitles[index].class == "dialogue" then
                table.insert(targets, index)
            end
        end
        table.sort(targets)
    elseif scope == SCOPE_FROM_CURRENT then
        for index = anchor_index, #subtitles do
            if subtitles[index].class == "dialogue" then
                table.insert(targets, index)
            end
        end
    elseif scope == SCOPE_ALL then
        for index = 1, #subtitles do
            if subtitles[index].class == "dialogue" then
                table.insert(targets, index)
            end
        end
    end

    return targets
end

local function find_anchor(subtitles, selected_lines, active_line)
    local first_index = nil
    for _, index in ipairs(selected_lines) do
        if subtitles[index].class == "dialogue"
            and (not first_index or index < first_index) then
            first_index = index
        end
    end

    local active = subtitles[active_line]
    if not first_index and active and active.class == "dialogue" then
        first_index = active_line
    end
    return first_index
end

local function shift_to_target(subtitles, selected_lines, active_line)
    local anchor_index = find_anchor(subtitles, selected_lines, active_line)
    if not anchor_index then
        show_message("请先选择至少一条字幕。")
        return selected_lines, active_line
    end

    local default_time = format_time(subtitles[anchor_index].start_time)

    local dialog = {
        {class = "label", label = "平移范围：", x = 0, y = 0},
        {
            class = "dropdown", name = "scope", x = 1, y = 0, width = 2,
            items = {SCOPE_SELECTED, SCOPE_FROM_CURRENT, SCOPE_ALL},
            value = SCOPE_FROM_CURRENT
        },
        {class = "label", label = "第一条所选字幕的新开始时间：", x = 0, y = 1},
        {
            class = "edit", name = "target_time", x = 1, y = 1, width = 2,
            value = default_time,
            hint = "例如 0:01:23.45；也可输入 1:23.450 或纯毫秒数"
        },
        {
            class = "label", x = 0, y = 2, width = 3,
            label = "偏移量 = 新时间 - 第一条所选字幕的原时间；开始和结束时间会一起平移。"
        }
    }

    local accepted, result = aegisub.dialog.display(dialog)
    if not accepted then
        return selected_lines, active_line
    end

    local target_time = parse_time(result.target_time)
    if not target_time then
        show_message("时间格式不正确。\n请输入例如 0:01:23.45、1:23.450，或纯毫秒数。")
        return selected_lines, active_line
    end

    local targets = collect_targets(
        subtitles, selected_lines, anchor_index, result.scope)
    if #targets == 0 then
        show_message("所选范围内没有字幕行。")
        return selected_lines, active_line
    end

    local anchor_time = subtitles[anchor_index].start_time
    local offset = target_time - anchor_time

    -- 先完整检查，再做任何修改，避免只改到一半。
    for _, index in ipairs(targets) do
        local line = subtitles[index]
        if line.start_time + offset < 0 or line.end_time + offset < 0 then
            show_message("无法平移：第 " .. index .. " 行平移后会早于 0:00:00.00。")
            return selected_lines, active_line
        end
    end

    for _, index in ipairs(targets) do
        local line = subtitles[index]
        line.start_time = line.start_time + offset
        line.end_time = line.end_time + offset
        subtitles[index] = line
    end

    aegisub.set_undo_point(script_name)
    return selected_lines, active_line
end

local function can_shift(subtitles, selected_lines, active_line)
    local active = active_line and subtitles[active_line]
    return active ~= nil and active.class == "dialogue"
end

aegisub.register_macro(script_name, script_description, shift_to_target, can_shift)
