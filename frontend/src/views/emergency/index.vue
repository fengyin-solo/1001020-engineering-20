<template>
  <section class="page" data-module="emergency">
    <header class="page-head">
      <div>
        <h2>应急抢险管理</h2>
        <p class="page-desc">维护应急事件，围绕事件编号、事件类型、发生地点、影响范围做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">事件上报</button>
        <button class="btn" type="button" @click="exportRows">导出应急抢险清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>事件编号</span>
        <input v-model="keyword" placeholder="按事件编号检索" />
      </label>
      <label class="filter-item">
        <span>事件状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无应急抢险数据，可先事件上报</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条应急抢险记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 事件上报 / 班组出动 / 处置结果 通用弹窗：三段链路共用一套表单结构 -->
    <div v-if="dialogVisible" class="modal-mask" @click.self="closeDialog">
      <form class="modal-panel" @submit.prevent="submitDialog">
        <h3 class="modal-title">{{ dialogTitle }}</h3>
        <label v-for="field in dialogFields" :key="field" class="modal-field">
          <span>{{ field }}</span>
          <textarea
            v-if="field === '处置结果'"
            v-model="dialogForm[field]"
            :rows="3"
            :placeholder="`请填写${field}`"
          ></textarea>
          <input v-else v-model="dialogForm[field]" :placeholder="`请填写${field}`" />
        </label>
        <p v-if="dialogHint" class="modal-hint">{{ dialogHint }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '确认提交' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/emergency'
const columns = ["事件编号", "事件类型", "发生地点", "影响范围", "响应等级", "出动班组", "处置结果", "事件状态"]
const actions = ["启动响应", "调集力量", "结束处置"]
const statuses = ["待响应", "响应中", "处置中", "已处置"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

// 各阶段的事件量：与后端状态口径保持一致，由接口按状态统计而不是写死。
const statusCounts = ref<Record<string, number>>({})
const stats = computed(() => [
  { label: "待响应事件", value: statusCounts.value["待响应"] ?? 0 },
  { label: "处置中事件", value: (statusCounts.value["响应中"] ?? 0) + (statusCounts.value["处置中"] ?? 0) },
  { label: "已处置事件", value: statusCounts.value["已处置"] ?? 0 },
])

// 弹窗状态：create 为事件上报，action 为状态流转动作；不同动作要求填的字段不同。
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'action'>('create')
const dialogAction = ref('')
const dialogTarget = ref<Row | null>(null)
const dialogForm = ref<Record<string, string>>({})
const submitting = ref(false)

const CREATE_FIELDS = ["事件编号", "事件类型", "发生地点", "影响范围", "响应等级"]
const ACTION_FIELDS: Record<string, string[]> = {
  启动响应: [],
  调集力量: ["出动班组"],
  结束处置: ["处置结果"],
}
const ACTION_HINTS: Record<string, string> = {
  启动响应: '启动响应后事件进入「响应中」，随后可调集班组出动。',
  调集力量: '请填写实际出动的抢险班组，出动后事件进入「处置中」。',
  结束处置: '请填写现场处置结论，提交后事件闭环为「已处置」。',
}

const dialogTitle = computed(() => dialogMode.value === 'create' ? '事件上报' : dialogAction.value)
const dialogFields = computed(() =>
  dialogMode.value === 'create' ? CREATE_FIELDS : ACTION_FIELDS[dialogAction.value] ?? [],
)
const dialogHint = computed(() =>
  dialogMode.value === 'action'
    ? ACTION_HINTS[dialogAction.value] ?? ''
    : '事件编号、事件类型、发生地点、响应等级为必填，提交后事件进入「待响应」。',
)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  dialogMode.value = 'create'
  dialogAction.value = ''
  dialogTarget.value = null
  dialogForm.value = { 事件编号: '', 事件类型: '', 发生地点: '', 影响范围: '', 响应等级: '' }
  dialogVisible.value = true
}

function runAction(action: string, row: Row) {
  dialogMode.value = 'action'
  dialogAction.value = action
  dialogTarget.value = row
  dialogForm.value = {
    出动班组: typeof row['出动班组'] === 'string' && row['出动班组'] !== '待出动' ? row['出动班组'] : '',
    处置结果: '',
  }
  dialogVisible.value = true
}

function closeDialog() {
  if (submitting.value) return
  dialogVisible.value = false
  dialogTarget.value = null
}

function buildQuery(status = ''): string {
  const params = new URLSearchParams()
  // 筛选时不带 status 参数；统计走各状态的独立查询，不要互相干扰。
  if (!status) {
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
    if (statusFilter.value) params.set('status', statusFilter.value)
  } else {
    params.set('status', status)
  }
  params.set('size', '200')
  return params.toString()
}

async function submitDialog() {
  errorMessage.value = ''
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const form = dialogForm.value
      // 后端必填：事件编号、事件类型、发生地点、响应等级；影响范围可留空。
      const missing = ["事件编号", "事件类型", "发生地点", "响应等级"]
        .filter((field) => !form[field]?.trim())
      if (missing.length) {
        errorMessage.value = `请填写${missing.join('、')}后再上报`
        return
      }
      const response = await request(ENDPOINT, {
        method: 'POST',
        body: JSON.stringify({ values: { ...form } }),
      })
      const payload = await response.json()
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message ?? '应急事件上报失败')
      }
    } else {
      const target = dialogTarget.value
      if (!target) return
      const fields = ACTION_FIELDS[dialogAction.value] ?? []
      const missing = fields.filter((field) => !dialogForm.value[field]?.trim())
      if (missing.length) {
        errorMessage.value = `请填写${missing.join('、')}后再提交`
        return
      }
      const values: Record<string, string> = { action: dialogAction.value }
      for (const field of fields) values[field] = dialogForm.value[field].trim()
      // 协议口径：动作与随附字段都放在 values 里，与后端 EntryPayload 对齐。
      const response = await request(`${ENDPOINT}/${target.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ values }),
      })
      const payload = await response.json()
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message ?? '应急抢险动作未生效')
      }
    }
    dialogVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '应急抢险操作失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const [listResponse, ...statusResponses] = await Promise.all([
      request(`${ENDPOINT}?${buildQuery()}`),
      ...statuses.map((status) => request(`${ENDPOINT}?${buildQuery(status)}`)),
    ])
    if (!listResponse.ok) {
      throw new Error('应急事件列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const counts: Record<string, number> = {}
    for (const [index, status] of statuses.entries()) {
      const response = statusResponses[index]
      if (response.ok) {
        const result = await response.json()
        counts[status] = result.total ?? 0
      }
    }
    statusCounts.value = counts
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '应急抢险列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-panel {
  width: 420px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
}

.modal-title {
  margin: 0 0 12px;
  font-size: 16px;
}

.modal-field {
  display: block;
  margin-bottom: 10px;
}

.modal-field span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}

.modal-field input,
.modal-field textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font: inherit;
}

.modal-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
