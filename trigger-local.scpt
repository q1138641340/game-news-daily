-- game-news-daily 本地定时运行 AppleScript
-- 每天北京时间 08:00 自动运行工作流

property workflowScript : "/Users/sunjinghe/daily-news-workflow/run-local.sh"
property targetHour : 8
property targetMinute : 0
property lastRunDate : missing value

on run
    display dialog "game-news-daily 本地工作流" buttons {"立即运行", "取消"} default button 1
    if button returned of result is "立即运行" then
        runWorkflow()
    end if
end run

on runWorkflow()
    set now to current date
    set currentSecond to seconds of now
    set currentMinute to minutes of now
    set currentHour to hours of now

    -- 检查是否已过 08:00
    set targetTime to targetHour * 3600 + targetMinute * 60
    set currentTime to currentHour * 3600 + currentMinute * 60

    if currentTime < targetTime then
        set waitSeconds to targetTime - currentTime
        display notification "下次运行: " & formatTime(targetHour, targetMinute) message "距离下次还有 " & (waitSeconds div 3600) & " 小时 " & ((waitSeconds mod 3600) div 60) & " 分钟"
    else
        display notification "game-news-daily 工作中..." message "正在运行日报收集..."
    end if

    -- 执行工作流脚本
    set sh to "bash " & quoted form of workflowScript & " 2>&1 | tee -a /Users/sunjinghe/daily-news-workflow/output/workflow.log"
    try
        set resultText to do shell script sh with administrator privileges
        display notification "工作流完成" message "已生成并同步到 iCloud vault"
    on error errStr
        display dialog "工作流失败: " & errStr buttons {"确定"} default button 1
    end try
end runWorkflow

on formatTime(h, m)
    if h < 12 then
        return (h as string) & ":" & (m as string) & " AM"
    else if h is 12 then
        return "12:" & (m as string) & " PM"
    else
        return ((h - 12) as string) & ":" & (m as string) & " PM"
    end if
end formatTime

on idle
    -- 每 60 秒检查一次
    set now to current date
    set currentHour to hours of now
    set currentMinute to minutes of now
    set currentSecond to seconds of now

    if currentHour is targetHour and currentMinute is targetMinute and currentSecond < 30 then
        runWorkflow()
    end if

    return 60
end idle