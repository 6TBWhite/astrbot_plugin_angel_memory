<template>
  <div>
    <h2 class="text-h5 mb-4">核心信念</h2>

    <v-alert type="info" variant="tonal" class="mb-4" density="compact">
      核心信念是 OC 在成长中形成的固定认知，会注入到每次对话中引导行为。
      可通过 WebUI 或管理员对话指令管理。
    </v-alert>

    <v-row v-if="loading">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" />
      </v-col>
    </v-row>

    <template v-else>
      <v-card class="mb-4">
        <v-card-title class="d-flex align-center">
          信念列表（{{ beliefs.length }} / 20 条上限）
          <v-spacer />
          <v-btn color="primary" size="small" prepend-icon="mdi-plus" @click="showAddDialog = true">
            新增
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-list v-if="beliefs.length" lines="two">
            <v-list-item v-for="belief in beliefs" :key="belief.id">
              <template #prepend>
                <v-icon color="primary">mdi-heart</v-icon>
              </template>
              <v-list-item-title>{{ belief.content }}</v-list-item-title>
              <v-list-item-subtitle>
                {{ belief.origin || '未知来源' }}
                <span v-if="belief.created_at"> | {{ formatTime(belief.created_at) }}</span>
              </v-list-item-subtitle>
              <template #append>
                <v-btn icon="mdi-pencil" size="small" variant="text" @click="openEdit(belief)" />
                <v-btn icon="mdi-delete" size="small" variant="text" color="error" @click="confirmDelete(belief)" />
              </template>
            </v-list-item>
          </v-list>
          <v-alert v-else type="info" variant="tonal">
            暂无核心信念。可以通过「新增」按钮或让管理员在对话中说「你以后跟不熟的人说话简短一点」来添加。
          </v-alert>
        </v-card-text>
      </v-card>

      <!-- 新增/编辑对话框 -->
      <v-dialog v-model="showAddDialog" max-width="500">
        <v-card>
          <v-card-title>{{ editingBelief ? '编辑信念' : '新增核心信念' }}</v-card-title>
          <v-card-text>
            <v-textarea
              v-model="formContent"
              label="信念内容"
              rows="3"
              auto-grow
              variant="outlined"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="closeDialog">取消</v-btn>
            <v-btn color="primary" :disabled="!formContent.trim()" @click="saveBelief">
              {{ editingBelief ? '保存' : '添加' }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 删除确认 -->
      <v-dialog v-model="showDeleteDialog" max-width="400">
        <v-card>
          <v-card-title>确认删除</v-card-title>
          <v-card-text>
            确定要删除信念「{{ deletingBelief?.content }}」吗？
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showDeleteDialog = false">取消</v-btn>
            <v-btn color="error" @click="deleteBelief">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useBridge } from '@/composables/useBridge'

const { apiGet, apiPost } = useBridge()

const loading = ref(true)
const beliefs = ref<any[]>([])
const showAddDialog = ref(false)
const showDeleteDialog = ref(false)
const editingBelief = ref<any>(null)
const deletingBelief = ref<any>(null)
const formContent = ref('')

async function loadBeliefs() {
  try {
    const data: any = await apiGet('beliefs')
    beliefs.value = data.beliefs || []
  } catch (e) {
    console.error('加载核心信念失败:', e)
  } finally {
    loading.value = false
  }
}

function openEdit(belief: any) {
  editingBelief.value = belief
  formContent.value = belief.content
  showAddDialog.value = true
}

function closeDialog() {
  showAddDialog.value = false
  editingBelief.value = null
  formContent.value = ''
}

async function saveBelief() {
  const content = formContent.value.trim()
  if (!content) return

  try {
    if (editingBelief.value) {
      await apiPost('beliefs/modify', { belief_id: editingBelief.value.id, content })
    } else {
      await apiPost('beliefs', { content })
    }
    closeDialog()
    await loadBeliefs()
  } catch (e) {
    console.error('保存信念失败:', e)
  }
}

function confirmDelete(belief: any) {
  deletingBelief.value = belief
  showDeleteDialog.value = true
}

async function deleteBelief() {
  if (!deletingBelief.value) return
  try {
    await apiPost('beliefs/delete', { belief_id: deletingBelief.value.id })
    showDeleteDialog.value = false
    deletingBelief.value = null
    await loadBeliefs()
  } catch (e) {
    console.error('删除信念失败:', e)
  }
}

function formatTime(ts: number): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(() => {
  loadBeliefs()
})
</script>
