<template>
  <div>
    <h2 class="text-h5 mb-4">👤 用户画像</h2>

    <v-row v-if="loading">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" />
      </v-col>
    </v-row>

    <template v-else>
      <!-- 用户列表 -->
      <v-card v-if="!selectedUser">
        <v-card-title>已识别用户（{{ users.length }}）</v-card-title>
        <v-card-text>
          <v-alert v-if="!users.length" type="info" variant="tonal">
            暂无用户画像数据。用户画像会在对话过程中自动生成。
          </v-alert>
          <v-row v-else>
            <v-col v-for="user in users" :key="user.user_id" cols="12" sm="6" md="4">
              <v-card
                variant="outlined"
                class="pa-3 cursor-pointer"
                hover
                @click="selectUser(user)"
              >
                <div class="d-flex align-center ga-3 mb-2">
                  <v-avatar color="primary" size="40">
                    <span class="text-body-1">{{ (user.nickname || user.user_id).charAt(0) }}</span>
                  </v-avatar>
                  <div>
                    <div class="text-body-1 font-weight-medium">
                      {{ user.nickname || '未知昵称' }}
                    </div>
                    <div class="text-caption text-grey">ID: {{ user.user_id }}</div>
                  </div>
                </div>
                <div class="d-flex flex-wrap ga-1 mt-2">
                  <v-chip
                    v-for="(count, attr) in user.attributes"
                    :key="attr"
                    size="x-small"
                    :color="attrColor(attr as string)"
                    variant="tonal"
                  >
                    {{ attr }} ({{ count }})
                  </v-chip>
                </div>
                <div class="text-caption text-grey mt-2">共 {{ user.memory_count }} 条画像记忆</div>
              </v-card>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- 用户详情 -->
      <template v-if="selectedUser">
        <v-btn
          variant="text"
          prepend-icon="mdi-arrow-left"
          class="mb-3"
          @click="selectedUser = null; profileMemories = []"
        >
          返回用户列表
        </v-btn>

        <v-card class="mb-4">
          <v-card-text class="d-flex align-center ga-4">
            <v-avatar color="primary" size="56">
              <span class="text-h6">{{ (selectedUser.nickname || selectedUser.user_id).charAt(0) }}</span>
            </v-avatar>
            <div>
              <div class="text-h6">{{ selectedUser.nickname || '未知昵称' }}</div>
              <div class="text-body-2 text-grey">用户 ID: {{ selectedUser.user_id }}</div>
              <div class="text-caption text-grey">共 {{ selectedUser.memory_count }} 条画像记忆</div>
            </div>
          </v-card-text>
          <v-divider />
          <v-card-text>
            <div class="d-flex align-center ga-4 mb-3">
              <span class="text-body-2 font-weight-medium">亲密度</span>
              <v-slider
                v-model="intimacyScore"
                :min="0"
                :max="1"
                :step="0.05"
                thumb-label
                hide-details
                density="compact"
                style="max-width: 200px"
                @end="saveIntimacy"
              />
              <v-chip size="small" :color="intimacyColor" variant="tonal">
                {{ intimacyLabel }}
              </v-chip>
            </div>
            <div class="mb-2">
              <span class="text-body-2 font-weight-medium">相处策略</span>
              <v-btn
                v-if="!editingStrategy"
                size="x-small"
                variant="text"
                icon="mdi-pencil"
                class="ml-2"
                @click="startEditStrategy"
              />
            </div>
            <template v-if="editingStrategy">
              <v-textarea
                v-model="strategyText"
                placeholder="输入相处策略..."
                rows="2"
                auto-grow
                variant="outlined"
                density="compact"
                hide-details
              />
              <div class="d-flex ga-2 mt-2">
                <v-btn size="x-small" color="primary" @click="saveStrategy">保存</v-btn>
                <v-btn size="x-small" variant="text" @click="editingStrategy = false">取消</v-btn>
              </div>
            </template>
            <div v-else-if="strategyText" class="text-body-2 mt-1">
              {{ strategyText }}
            </div>
            <div v-else class="text-body-2 text-grey mt-1">
              暂无策略。管理员可在对话中说「跟张三别太热情」来设置。
            </div>
            <div v-if="strategySource" class="text-caption text-grey mt-1">
              {{ strategySource }}
            </div>
          </v-card-text>
        </v-card>

        <v-progress-linear v-if="profileLoading" indeterminate color="primary" class="mb-4" />

        <!-- 按属性分组展示 -->
        <template v-for="attr in attributeOrder" :key="attr">
          <v-card v-if="groupedMemories[attr]?.length" class="mb-4">
            <v-card-title>
              <v-chip :color="attrColor(attr)" size="small" class="mr-2">{{ attr }}</v-chip>
              {{ groupedMemories[attr].length }} 条
            </v-card-title>
            <v-card-text>
              <v-list density="compact">
                <v-list-item
                  v-for="mem in groupedMemories[attr]"
                  :key="mem.id"
                  class="mb-2"
                >
                  <v-card variant="tonal" class="pa-3">
                    <div class="d-flex align-center ga-2 mb-1">
                      <v-icon
                        :icon="mem.is_active ? 'mdi-star' : 'mdi-star-outline'"
                        :color="mem.is_active ? 'amber' : 'grey'"
                        size="small"
                      />
                      <v-chip size="x-small" :color="strengthColor(mem.strength)">
                        强度 {{ mem.strength }}
                      </v-chip>
                      <span class="text-caption text-grey">{{ formatTime(mem.updated_at) }}</span>
                    </div>
                    <div class="text-body-2 font-weight-medium">{{ mem.judgment }}</div>
                    <div v-if="mem.reasoning" class="text-caption text-grey mt-1">{{ mem.reasoning }}</div>
                    <div class="d-flex flex-wrap ga-1 mt-2">
                      <v-chip
                        v-for="tag in parseTags(mem.tags)"
                        :key="tag"
                        size="x-small"
                        :color="tagColor(tag)"
                        variant="tonal"
                      >
                        {{ tag }}
                      </v-chip>
                    </div>
                  </v-card>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </template>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useBridge } from '@/composables/useBridge'

const { apiGet, apiPost } = useBridge()

const loading = ref(true)
const users = ref<any[]>([])
const selectedUser = ref<any>(null)
const profileMemories = ref<any[]>([])
const profileLoading = ref(false)

const intimacyScore = ref(0)
const strategyText = ref('')
const strategySource = ref('')
const editingStrategy = ref(false)

const attributeOrder = ['用户别名', '事实属性', '技能树', '关系图谱', '活跃项目']

const groupedMemories = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const mem of profileMemories.value) {
    const attr = mem.attribute || '其他'
    if (!groups[attr]) groups[attr] = []
    groups[attr].push(mem)
  }
  return groups
})

function attrColor(attr: string): string {
  const map: Record<string, string> = {
    '用户别名': 'blue',
    '事实属性': 'green',
    '技能树': 'purple',
    '关系图谱': 'orange',
    '活跃项目': 'cyan',
  }
  return map[attr] || 'grey'
}

function strengthColor(s: number): string {
  if (s >= 80) return 'success'
  if (s >= 50) return 'primary'
  if (s >= 30) return 'warning'
  return 'error'
}

function formatTime(ts: number | null): string {
  if (!ts) return '-'
  let t = Number(ts)
  if (t > 1e11) t /= 1000
  return new Date(t * 1000).toLocaleString('zh-CN')
}

function parseTags(tags: string): string[] {
  if (!tags) return []
  return tags.split(',').map(t => t.trim()).filter(Boolean)
}

function tagColor(tag: string): string {
  const attrColors: Record<string, string> = {
    '用户别名': 'blue',
    '事实属性': 'green',
    '技能树': 'purple',
    '关系图谱': 'orange',
    '活跃项目': 'cyan',
  }
  if (attrColors[tag]) return attrColors[tag]
  if (/^\d{6,}$/.test(tag)) return 'grey'
  return 'primary'
}

async function selectUser(user: any) {
  selectedUser.value = user
  profileLoading.value = true
  editingStrategy.value = false
  try {
    const data: any = await apiGet('profiles/detail', { user_id: user.user_id })
    profileMemories.value = data.memories || []
    await loadStrategy(user.user_id, user.nickname)
  } catch (e) {
    console.error('加载用户画像失败:', e)
  } finally {
    profileLoading.value = false
  }
}

async function loadStrategy(userId: string, nickname?: string) {
  try {
    const params: Record<string, string> = { user_id: userId }
    if (nickname) params.nickname = nickname
    const data: any = await apiGet('profiles/strategy', params)
    const strategy = data.strategy || {}
    strategyText.value = strategy.strategy || ''
    strategySource.value = strategy.source || ''
    intimacyScore.value = data.intimacy || 0
  } catch (e) {
    strategyText.value = ''
    strategySource.value = ''
    intimacyScore.value = 0
  }
}

const intimacyLabel = computed(() => {
  const s = intimacyScore.value
  if (s < 0.3) return '不太熟'
  if (s < 0.6) return '一般'
  if (s < 0.8) return '比较熟'
  return '很熟'
})

const intimacyColor = computed(() => {
  const s = intimacyScore.value
  if (s < 0.3) return 'grey'
  if (s < 0.6) return 'info'
  if (s < 0.8) return 'success'
  return 'pink'
})

function startEditStrategy() {
  editingStrategy.value = true
}

async function saveStrategy() {
  if (!selectedUser.value) return
  try {
    await apiPost('profiles/strategy', {
      user_id: selectedUser.value.user_id,
      strategy: strategyText.value,
      intimacy: intimacyScore.value,
    })
    editingStrategy.value = false
    await loadStrategy(selectedUser.value.user_id)
  } catch (e) {
    console.error('保存策略失败:', e)
  }
}

async function saveIntimacy() {
  if (!selectedUser.value) return
  try {
    await apiPost('profiles/strategy', {
      user_id: selectedUser.value.user_id,
      intimacy: intimacyScore.value,
    })
    await loadStrategy(selectedUser.value.user_id)
  } catch (e) {
    console.error('保存亲密度失败:', e)
  }
}

onMounted(async () => {
  try {
    const data: any = await apiGet('profiles')
    users.value = data.users || []
  } catch (e) {
    console.error('加载用户列表失败:', e)
  } finally {
    loading.value = false
  }
})
</script>
