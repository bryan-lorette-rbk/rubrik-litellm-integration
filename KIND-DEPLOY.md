## Step 1: Create the kind Cluster (with Port Forwarding)

We need to tell kind to map your machine's port 80 to the internal cluster network so the Ingress controller can receive traffic.

Create a file named kind-config.yaml:

```YAML
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  # This maps your localhost:80 to the kind node's port 80
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
```

Now, create the cluster:

```Bash
kind create cluster --name litellm-local --config ./kube-setup/kind-config.yaml
```

## Step 2: Install the F5 NGINX Ingress Controller
Since you want the proper F5 NGINX controller (nginxinc/kubernetes-ingress), the easiest way to install it is via Helm. We will configure it to use the host network so it binds directly to the port 80 we just exposed.

Run these commands:

```Bash

helm install nginx-ingress ./kube-setup/nginx-ingress \
  --namespace nginx-ingress --create-namespace \
  -f ./kube-setup/nginx-simple-vals.yaml
```

Wait a minute or two for the NGINX pod to spin up. You can check its status with kubectl get pods -n nginx-ingress.

## Step 3: Deploy Lite LLM

**Option 1**

1. Apply the Secrets first
The deployment will fail to start if the secrets aren't already present in the cluster.
```Bash
kubectl apply -f ./kube-setup/litellm/secrets.yaml
```

2. Apply the ConfigMaps
This loads both your config.yaml and your custom_plugin.py into the cluster.
```Bash
kubectl apply -f ./kube-setup/litellm/litellm-configmap.yaml
kubectl apply -f ./kube-setup/litellm/plugin-configmap.yaml
```

3. Apply the Deployment
Now that the dependencies are in place, spin up the LiteLLM pods.
```Bash
kubectl apply -f ./kube-setup/litellm/deployment.yaml
```

4. Apply the Networking (Service & Ingress)
Finally, wire up the internal routing and expose it to your NGINX controller.
```Bash
kubectl apply -f ./kube-setup/litellm/service.yaml
kubectl apply -f ./kube-setup/litellm/ingress.yaml
```
(Pro-tip: If you keep all these files in their own dedicated folder, you can actually just run kubectl apply -f . and Kubernetes is usually smart enough to sort out the creation order, but doing it manually the first time guarantees no race conditions).

**Verifying the Deployment**
Give it about 15–30 seconds to pull the image and run the health probes. You can watch the progress with:
```Bash
kubectl get pods -w
```

Once both pods show 2/2 or 1/1 under the READY column, check that your Ingress successfully grabbed an IP address (or bound to localhost if you are on kind):
```Bash
kubectl get ingress litellm-ingress
```

**Option 2**
Build & Sideload Your Custom Image
Because we aren't pushing your custom image to a public registry (like Docker Hub), kind will fail to pull it. We need to build it locally and "sideload" it directly into the kind node.

Build the image (using the Dockerfile from our previous step):

```Bash
docker build -t litellm-custom-proxy:local .
```
Load it into the cluster:

```Bash
kind load docker-image litellm-custom-proxy:local --name litellm-local
```

## Step 4: Update Your Deployment YAML
Before you apply your Kubernetes files, you need to make one small tweak to your 3-deployment.yaml.

Change the imagePullPolicy to Never or IfNotPresent. If you leave it as Always, Kubernetes will try to reach out to the internet to find litellm-custom-proxy:local, fail, and throw an ImagePullBackOff error.

```YAML
# Inside 3-deployment.yaml
      containers:
        - name: litellm
          image: litellm-custom-proxy:local
          imagePullPolicy: IfNotPresent  # <--- CRITICAL FOR LOCAL DEV
          args:
            - "--config"
            - "/app/config.yaml"
# ... the rest of the file
```
## Step 5: Deploy to the Cluster
Assuming you have your 1-secrets.yaml, 2-configmaps.yaml (just the litellm-config), 3-deployment.yaml, and 4-network.yaml in the same directory, run:

```Bash
kubectl apply -f .
```
Verify everything is running:

```Bash
kubectl get pods
kubectl get ingress
```

## Step 6: Test It!
Since your Ingress is configured to route traffic for litellm.yourdomain.com, you have two ways to test this locally.

**Option A (Quick and dirty):**
Pass the Host header directly in your curl command to trick NGINX into routing it:

```Bash
curl -H "Host: litellm.yourdomain.com" http://localhost/health/liveliness
```

**Option B (The proper local way):**
Add the domain to your machine's hosts file so your browser knows where to go.

Open /etc/hosts (Mac/Linux) or C:\Windows\System32\drivers\etc\hosts (Windows) as an administrator.

Add this line to the bottom:
127.0.0.1 litellm.yourdomain.com

Can use this in agents, etc. To make it simple for the API Key can just use your master key. 


## Clean Up: The Nuclear Option (Destroy the Kind Cluster)
If you spun this up locally using kind and you are completely done experimenting for the day, there is no need to delete the individual files. You can just destroy the entire virtual cluster.

This will wipe out everything—LiteLLM, NGINX, and the cluster itself:

```Bash
kind delete cluster --name litellm-local
```