param(
    [ValidateSet('Install', 'Compile', 'Benchmark', 'Baseline')]
    [string]$Action = 'Install',
    [double]$Seconds = 30,
    [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $HOME '.codex/runtimes/ovni-20261009'
$tools = Join-Path $root 'work/ovni-runtime-2026-10-09'
$source = Join-Path $root 'work/ovni-evaluation-2026-10-09'
$mamba = Join-Path $tools 'Library/bin/micromamba.exe'
$python = Join-Path $runtime 'python.exe'
$commit = '6d82e678667d438162fe52f76de4666991d4c424'

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe" }
}

Push-Location $root
try {
    if ($Action -eq 'Install') {
        New-Item -ItemType Directory -Path $tools -Force | Out-Null
        if (-not (Test-Path -LiteralPath $mamba)) {
            $archive = Join-Path $tools 'micromamba.tar.bz2'
            Invoke-WebRequest -Uri 'https://micro.mamba.pm/api/micromamba/win-64/latest' -OutFile $archive
            Invoke-Checked 'tar' @('xf', $archive, '-C', $tools, 'Library/bin/micromamba.exe')
        }
        if (-not (Test-Path -LiteralPath $source)) {
            Invoke-Checked 'git' @('clone', 'https://github.com/billythegoat356/OVNI.git', $source)
            Invoke-Checked 'git' @('-C', $source, 'checkout', '--detach', $commit)
        }
        $actual = & git -C $source rev-parse HEAD
        if ($LASTEXITCODE -ne 0 -or $actual -ne $commit) { throw 'Unexpected OVNI source revision' }
        $env:MAMBA_ROOT_PREFIX = Join-Path $HOME '.codex/ovni-mamba'
        Invoke-Checked $mamba @('create', '-p', $runtime, '-c', 'conda-forge', '--override-channels',
                               'python=3.11', 'pycuda=2025.1.1', 'cupy=13.6.0', 'cuda-version=12.9',
                               'cuda-nvcc=12.9', 'pip', '-y', '--quiet')
    }
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run -Action Install first' }
    # Process-local paths only: never replace studio Python or system NVIDIA drivers.
    $env:PATH = "$runtime;$runtime/Library/bin;$runtime/Scripts;" + $env:PATH
    $env:CONDA_PREFIX = $runtime
    $env:CUDA_PATH = Join-Path $runtime 'Library'
    if ($Action -eq 'Install') {
        Invoke-Checked $python @('-m', 'pip', 'install', 'numpy==2.2.6', 'PyNvVideoCodec==2.0.1',
                                'pillow==11.2.1', 'opencv-python==4.11.0.86')
        Invoke-Checked $python @('-m', 'pip', 'install', '--no-deps', $source)
        Invoke-Checked $python @('-m', 'pip', 'check')
    }
    if ($Action -in @('Install', 'Compile')) {
        Invoke-Checked $python @('production/ovni_smoke.py', 'compile', '--source', $source)
    }
    if ($Action -in @('Benchmark', 'Baseline')) {
        if (-not $Output) { throw 'Choose a fresh -Output directory for the technical test' }
        $studioPython = Join-Path $root 'venv/Scripts/python.exe'
        $ffmpeg = & $studioPython -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
        if ($LASTEXITCODE -ne 0) { throw 'Studio FFmpeg not available for muxing' }
        $excerpt = 'work/historical-01-2026-10-08/edo-daily/review-excerpt'
        $arguments = @('--timeline', "$excerpt/timeline.json", '--approval', "$excerpt/format-review.json",
                       '--audio', "$excerpt/excerpt.mp3", '--ffmpeg', $ffmpeg,
                       '--output', $Output, '--seconds', "$Seconds")
        if ($Action -eq 'Benchmark') {
            Invoke-Checked $python (@('production/ovni_smoke.py', 'benchmark') + $arguments)
        } else {
            Invoke-Checked $studioPython (@('production/ovni_baseline.py') + $arguments)
        }
    }
} finally {
    Pop-Location
}
