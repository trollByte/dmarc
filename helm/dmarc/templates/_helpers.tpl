{{/*
Expand the name of the chart.
*/}}
{{- define "dmarc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "dmarc.fullname" -}}
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
{{- define "dmarc.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "dmarc.labels" -}}
helm.sh/chart: {{ include "dmarc.chart" . }}
{{ include "dmarc.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "dmarc.selectorLabels" -}}
app.kubernetes.io/name: {{ include "dmarc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "dmarc.backend.labels" -}}
{{ include "dmarc.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "dmarc.backend.selectorLabels" -}}
{{ include "dmarc.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "dmarc.frontend.labels" -}}
{{ include "dmarc.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "dmarc.frontend.selectorLabels" -}}
{{ include "dmarc.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Worker labels
*/}}
{{- define "dmarc.worker.labels" -}}
{{ include "dmarc.labels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "dmarc.worker.selectorLabels" -}}
{{ include "dmarc.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Beat labels
*/}}
{{- define "dmarc.beat.labels" -}}
{{ include "dmarc.labels" . }}
app.kubernetes.io/component: beat
{{- end }}

{{/*
Beat selector labels
*/}}
{{- define "dmarc.beat.selectorLabels" -}}
{{ include "dmarc.selectorLabels" . }}
app.kubernetes.io/component: beat
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "dmarc.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "dmarc.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "dmarc.backend.image" -}}
{{- $registry := .Values.global.imageRegistry | default "" -}}
{{- $repository := .Values.backend.image.repository -}}
{{- $tag := .Values.backend.image.tag | default .Chart.AppVersion -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "dmarc.frontend.image" -}}
{{- $registry := .Values.global.imageRegistry | default "" -}}
{{- $repository := .Values.frontend.image.repository -}}
{{- $tag := .Values.frontend.image.tag | default .Chart.AppVersion -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Database URL
*/}}
{{- define "dmarc.databaseUrl" -}}
{{- if .Values.postgresql.enabled -}}
postgresql://{{ .Values.postgresql.auth.username }}:$(DATABASE_PASSWORD)@{{ include "dmarc.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else -}}
postgresql://{{ .Values.externalDatabase.username }}:$(DATABASE_PASSWORD)@{{ .Values.externalDatabase.host }}:{{ .Values.externalDatabase.port }}/{{ .Values.externalDatabase.database }}
{{- end -}}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "dmarc.redisUrl" -}}
{{- if .Values.redis.enabled -}}
redis://:$(REDIS_PASSWORD)@{{ include "dmarc.fullname" . }}-redis-master:6379/0
{{- else -}}
redis://:$(REDIS_PASSWORD)@{{ .Values.externalRedis.host }}:{{ .Values.externalRedis.port }}/0
{{- end -}}
{{- end }}
