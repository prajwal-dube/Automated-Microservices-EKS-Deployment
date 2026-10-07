{{- define "netops.name" -}}
{{- printf "%s-netops" .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}
{{- define "netops.labels" -}}
app.kubernetes.io/name: netops
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "netops.security" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}
{{- define "netops.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
{{- define "netops.dbEnv" -}}
- name: DB_HOST
  value: {{ printf "%s-postgres" (include "netops.name" .) | quote }}
- name: DB_NAME
  value: netops
- name: DB_USER
  value: netops
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecret }}
      key: DB_PASSWORD
{{- end -}}
