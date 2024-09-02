# ============================================================
#  Healthcare DataScience Platform
#  GitHub Repository Status Checker
#  Usage: .\github-check.ps1
# ============================================================
# NOTE: TOKEN is loaded from master-config.bat at runtime.
# Run this script from the project root.

# Load token from master-config.bat
$configPath = Join-Path $PSScriptRoot "master-config.bat"
$ghToken    = $null
$ghUser     = "SiddiqueDataEng"
$repoName   = "Healthcare-DataScience-Platform"

if (Test-Path $configPath) {
    Get-Content $configPath | ForEach-Object {
        if ($_ -match 'set "MASTER_GITHUB_TOKEN=(.+)"') { $ghToken = $Matches[1] }
        if ($_ -match 'set "MASTER_GITHUB_USER=(.+)"')  { $ghUser  = $Matches[1] }
    }
}

if (-not $ghToken) {
    Write-Host "ERROR: Could not read MASTER_GITHUB_TOKEN from master-config.bat" -ForegroundColor Red
    exit 1
}

$repoSlug = "$ghUser/$repoName"
$apiBase  = "https://api.github.com"

$ghHeaders = @{
    Authorization = "token $ghToken"
    Accept        = "application/vnd.github+json"
    "User-Agent"  = "Healthcare-DataScience-Platform"
}

function Invoke-GH {
    param([string]$path)
    $uri = $apiBase + "/" + $path
    try {
        Invoke-RestMethod -Uri $uri -Headers $ghHeaders -ErrorAction Stop
    } catch {
        Write-Host ("  ERROR [$path]: " + $_.Exception.Message) -ForegroundColor Red
        $null
    }
}

function Trim-Str($s, $n) {
    if (-not $s) { return "" }
    if ($s.Length -le $n) { return $s }
    return $s.Substring(0, $n) + "..."
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Healthcare DataScience Platform -- GitHub Status" -ForegroundColor Cyan
Write-Host "  https://github.com/$repoSlug" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# --- Repo overview ---
$repoInfo = Invoke-GH "repos/$repoSlug"
if ($repoInfo) {
    Write-Host ""
    Write-Host "=== REPOSITORY ===" -ForegroundColor Yellow
    Write-Host ("  name        : " + $repoInfo.full_name)
    Write-Host ("  description : " + $repoInfo.description)
    Write-Host ("  branch      : " + $repoInfo.default_branch)
    Write-Host ("  pushed_at   : " + $repoInfo.pushed_at)
    Write-Host ("  language    : " + $repoInfo.language)
    Write-Host ("  stars       : " + $repoInfo.stargazers_count)
    Write-Host ("  forks       : " + $repoInfo.forks_count)
    Write-Host ("  open_issues : " + $repoInfo.open_issues_count)
}

# --- Recent commits ---
Write-Host ""
Write-Host "=== RECENT COMMITS ===" -ForegroundColor Yellow
$commits = Invoke-GH ("repos/" + $repoSlug + "/commits?per_page=8")
foreach ($c in @($commits)) {
    if ($c -and $c.commit) {
        $dt   = $c.commit.author.date.Substring(0, 10)
        $msg  = Trim-Str $c.commit.message.Split("`n")[0] 70
        $auth = $c.commit.author.name
        Write-Host ("  $dt  [$auth]  $msg")
    }
}

# --- Issues ---
$issueData = Invoke-GH ("repos/" + $repoSlug + "/issues?state=open&per_page=100")
$issueList = @($issueData) | Where-Object { $_ -and (-not $_.pull_request) }
Write-Host ""
Write-Host ("=== OPEN ISSUES (" + $issueList.Count + ") ===") -ForegroundColor Yellow
foreach ($i in ($issueList | Select-Object -First 15)) {
    $lbs = ($i.labels | ForEach-Object { $_.name }) -join ", "
    Write-Host ("  #" + $i.number + "  " + (Trim-Str $i.title 55) + "  [$lbs]")
}

# --- Milestones ---
$msData = Invoke-GH ("repos/" + $repoSlug + "/milestones?per_page=10&state=open")
$msList = @($msData) | Where-Object { $_ }
Write-Host ""
Write-Host ("=== MILESTONES (" + $msList.Count + ") ===") -ForegroundColor Yellow
foreach ($m in $msList) {
    $due = if ($m.due_on) { $m.due_on.Substring(0,10) } else { "no due date" }
    Write-Host ("  " + (Trim-Str $m.title 40) + " | due $due | open=$($m.open_issues) closed=$($m.closed_issues)")
}

# --- Pull Requests ---
$prData = Invoke-GH ("repos/" + $repoSlug + "/pulls?state=all&per_page=10")
$prList = @($prData) | Where-Object { $_ }
Write-Host ""
Write-Host ("=== PULL REQUESTS (" + $prList.Count + ") ===") -ForegroundColor Yellow
foreach ($p in $prList) {
    $st = $p.state.ToUpper()
    Write-Host ("  #" + $p.number + " [$st]  " + (Trim-Str $p.title 60))
}

# --- Releases ---
$relData = Invoke-GH ("repos/" + $repoSlug + "/releases?per_page=5")
$relList = @($relData) | Where-Object { $_ }
Write-Host ""
Write-Host ("=== RELEASES (" + $relList.Count + ") ===") -ForegroundColor Yellow
foreach ($r in $relList) {
    $pub = if ($r.published_at) { $r.published_at.Substring(0,10) } else { "draft" }
    Write-Host ("  " + $r.tag_name + " | " + (Trim-Str $r.name 50) + " | $pub")
}

# --- Labels ---
$lblData = Invoke-GH ("repos/" + $repoSlug + "/labels?per_page=50")
$lblList = @($lblData) | Where-Object { $_ }
Write-Host ""
Write-Host ("=== LABELS (" + $lblList.Count + ") ===") -ForegroundColor Yellow
foreach ($l in $lblList) {
    Write-Host ("  #" + $l.color + "  " + $l.name)
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Done." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
