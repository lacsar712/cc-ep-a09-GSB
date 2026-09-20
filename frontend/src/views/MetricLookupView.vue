<template>
  <div class="page">
    <h1 style="margin-bottom: 4px">指标检索</h1>
    <p class="muted" style="margin-top: 0">按指标名精确查找记录过该指标的 Run</p>

    <div class="card" style="margin-bottom: 16px">
      <n-form-item label="指标名" :show-feedback="false">
        <n-input
          v-model:value="metricName"
          clearable
          placeholder="例如 tm_score"
          @keyup.enter="search"
        />
      </n-form-item>
      <n-button style="margin-top: 8px" type="primary" :loading="loading" @click="search">
        查询
      </n-button>
    </div>

    <div v-if="searched" class="card">
      <p class="muted" style="margin-top: 0">
        指标 <span class="mono">{{ lastQuery }}</span> 共命中 {{ rows.length }} 条 Run
      </p>
      <n-data-table :columns="columns" :data="rows" :loading="loading" :bordered="false" />
    </div>
  </div>
</template>

<script setup>
import { h, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { lookupMetricRuns } from '../api/client'

const router = useRouter()
const message = useMessage()
const metricName = ref('')
const lastQuery = ref('')
const rows = ref([])
const loading = ref(false)
const searched = ref(false)

const statusMap = {
  running: { type: 'info', label: '进行中' },
  completed: { type: 'success', label: '已完成' },
  aborted: { type: 'warning', label: '已中止' },
}

const columns = [
  { title: '项目', key: 'project' },
  { title: '名称', key: 'name' },
  {
    title: '状态',
    key: 'status',
    render(row) {
      const m = statusMap[row.status] || { type: 'default', label: row.status }
      return h(NTag, { type: m.type, size: 'small' }, { default: () => m.label })
    },
  },
  { title: '最近值', key: 'value' },
  { title: 'step', key: 'step', width: 80 },
  {
    title: '记录时间',
    key: 'recorded_at',
    render(row) {
      return row.recorded_at ? new Date(row.recorded_at).toLocaleString() : '—'
    },
  },
  {
    title: '操作',
    key: 'actions',
    render(row) {
      return h(
        NButton,
        { size: 'tiny', onClick: () => router.push(`/runs/${row.run_id}`) },
        { default: () => '详情' },
      )
    },
  },
]

async function search() {
  const name = metricName.value.trim()
  if (!name) {
    message.warning('请输入指标名')
    return
  }
  loading.value = true
  try {
    rows.value = await lookupMetricRuns(name)
    lastQuery.value = name
    searched.value = true
  } catch (e) {
    message.error(e.message || '查询失败')
  } finally {
    loading.value = false
  }
}
</script>
