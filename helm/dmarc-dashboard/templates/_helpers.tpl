{{/*
Expand the name of the chart.
*/}}
{{- define "dmarc-dashboard.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "dmarc-dashboard.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "dmarc-dashboard.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "dmarc-dashboard.labels" -}}
helm.sh/chart: {{ include "dmarc-dashboard.chart" . }}
{{ include "dmarc-dashboard.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "dmarc-dashboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dmarc-dashboard.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "dmarc-dashboard.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "dmarc-dashboard.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL
*/}}
{{- define "dmarc-dashboard.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
postgresql://{{ .Values.secrets.dbUser }}:{{ .Values.secrets.dbPassword }}@{{ include "dmarc-dashboard.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else }}
postgresql://{{ .Values.secrets.dbUser }}:{{ .Values.secrets.dbPassword }}@{{ .Values.postgresql.externalHost }}:{{ .Values.postgresql.externalPort }}/{{ .Values.postgresql.auth.database }}
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "dmarc-dashboard.redisUrl" -}}
{{- if .Values.redis.enabled }}
redis://{{ include "dmarc-dashboard.fullname" . }}-redis-master:6379/0
{{- else }}
redis://{{ .Values.redis.externalHost }}:{{ .Values.redis.externalPort }}/0
{{- end }}
{{- end }}

{{/*
Celery Broker URL
*/}}
{{- define "dmarc-dashboard.celeryBrokerUrl" -}}
{{- if .Values.redis.enabled }}
redis://{{ include "dmarc-dashboard.fullname" . }}-redis-master:6379/1
{{- else }}
redis://{{ .Values.redis.externalHost }}:{{ .Values.redis.externalPort }}/1
{{- end }}
{{- end }}
