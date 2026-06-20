param(
    [string]$ClusterName = "localrag"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

foreach ($command in @("docker", "kubectl")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command '$command' is not installed or not available on PATH."
    }
}

$KindCommand = (Get-Command kind -ErrorAction SilentlyContinue).Source
if (-not $KindCommand) {
    $KindCommand = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Recurse -Filter kind.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $KindCommand) {
    throw "Required command 'kind' is not installed or not available on PATH."
}

Push-Location $ProjectRoot
try {
    $clusters = & $KindCommand get clusters
    if ($clusters -notcontains $ClusterName) {
        & $KindCommand create cluster --name $ClusterName --config k8s/kind-config.yaml
    }

    docker build -t localrag-backend:dev ./backend
    docker build -t localrag-frontend:dev ./frontend
    & $KindCommand load docker-image localrag-backend:dev localrag-frontend:dev --name $ClusterName

    kubectl create namespace localrag --dry-run=client -o yaml | kubectl apply -f -
    kubectl create secret generic localrag-secrets `
        --namespace localrag `
        --from-literal=POSTGRES_PASSWORD=local_development_only `
        --from-literal=DATABASE_URL=postgresql://retrieval:local_development_only@postgres:5432/retrieval `
        --dry-run=client -o yaml | kubectl apply -f -

    kubectl apply -k k8s/base
    kubectl rollout status statefulset/postgres -n localrag --timeout=5m
    kubectl rollout status deployment/redis -n localrag --timeout=5m
    kubectl rollout status deployment/ollama -n localrag --timeout=5m
    kubectl wait --for=condition=complete job/model-loader -n localrag --timeout=20m
    kubectl rollout status deployment/backend -n localrag --timeout=5m
    kubectl rollout status deployment/worker -n localrag --timeout=5m
    kubectl rollout status deployment/frontend -n localrag --timeout=5m

    kubectl get pods -n localrag
    Write-Host "Deployment completed. Run .\scripts\port-forward-kubernetes.ps1 to open the application."
}
finally {
    Pop-Location
}
