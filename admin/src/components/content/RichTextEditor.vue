<template>
  <div class="rich-text-editor" :class="{ 'rich-text-editor--disabled': disabled }">
    <div class="rich-text-editor__toolbar">
      <Button
        type="button"
        label="Paragraph"
        size="small"
        :disabled="disabled"
        :severity="isParagraphActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="setParagraph"
      />
      <Button
        type="button"
        label="H2"
        size="small"
        :disabled="disabled"
        :severity="isHeadingTwoActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleHeading(2)"
      />
      <Button
        type="button"
        label="H3"
        size="small"
        :disabled="disabled"
        :severity="isHeadingThreeActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleHeading(3)"
      />
      <Button
        type="button"
        icon="pi pi-bold"
        size="small"
        :disabled="disabled"
        :severity="isBoldActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleBold"
      />
      <Button
        type="button"
        icon="pi pi-italic"
        size="small"
        :disabled="disabled"
        :severity="isItalicActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleItalic"
      />
      <Button
        type="button"
        label="Strike"
        size="small"
        :disabled="disabled"
        :severity="isStrikeActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleStrike"
      />
      <Button
        type="button"
        label="Quote"
        size="small"
        :disabled="disabled"
        :severity="isBlockquoteActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleBlockquote"
      />
      <Button
        type="button"
        label="Bullets"
        size="small"
        :disabled="disabled"
        :severity="isBulletListActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleBulletList"
      />
      <Button
        type="button"
        label="Numbers"
        size="small"
        :disabled="disabled"
        :severity="isOrderedListActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleOrderedList"
      />
      <Button
        type="button"
        label="Code"
        size="small"
        :disabled="disabled"
        :severity="isCodeBlockActive ? 'contrast' : 'secondary'"
        variant="outlined"
        @click="toggleCodeBlock"
      />
      <Button
        type="button"
        label="Rule"
        size="small"
        :disabled="disabled"
        severity="secondary"
        variant="outlined"
        @click="insertHorizontalRule"
      />
      <Button
        type="button"
        icon="pi pi-undo"
        size="small"
        :disabled="disabled || !canUndo"
        severity="secondary"
        variant="outlined"
        @click="undo"
      />
      <Button
        type="button"
        icon="pi pi-replay"
        size="small"
        :disabled="disabled || !canRedo"
        severity="secondary"
        variant="outlined"
        @click="redo"
      />
    </div>

    <EditorContent :editor="editor" class="rich-text-editor__content" />

    <small class="muted rich-text-editor__hint">
      Stored output is restricted to the Pragma rich-text HTML contract: paragraphs, headings, emphasis, lists, blockquotes, code, hard breaks, and horizontal rules.
    </small>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import Button from 'primevue/button'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/vue-3'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  immediatelyRender: false,
  extensions: [StarterKit],
  editorProps: {
    attributes: {
      class: 'rich-text-editor__input',
      spellcheck: 'true',
    },
  },
  onUpdate: ({ editor: currentEditor }) => {
    emit('update:modelValue', currentEditor.getHTML())
  },
})

const isParagraphActive = computed(() => editor.value?.isActive('paragraph') ?? false)
const isHeadingTwoActive = computed(() => editor.value?.isActive('heading', { level: 2 }) ?? false)
const isHeadingThreeActive = computed(() => editor.value?.isActive('heading', { level: 3 }) ?? false)
const isBoldActive = computed(() => editor.value?.isActive('bold') ?? false)
const isItalicActive = computed(() => editor.value?.isActive('italic') ?? false)
const isStrikeActive = computed(() => editor.value?.isActive('strike') ?? false)
const isBlockquoteActive = computed(() => editor.value?.isActive('blockquote') ?? false)
const isBulletListActive = computed(() => editor.value?.isActive('bulletList') ?? false)
const isOrderedListActive = computed(() => editor.value?.isActive('orderedList') ?? false)
const isCodeBlockActive = computed(() => editor.value?.isActive('codeBlock') ?? false)
const canUndo = computed(() => editor.value?.can().chain().focus().undo().run() ?? false)
const canRedo = computed(() => editor.value?.can().chain().focus().redo().run() ?? false)

watch(
  () => props.modelValue,
  (value) => {
    const currentEditor = editor.value
    if (!currentEditor) {
      return
    }

    const nextValue = value ?? ''
    if (currentEditor.getHTML() === nextValue) {
      return
    }

    currentEditor.commands.setContent(nextValue, false)
  },
)

watch(
  () => props.disabled,
  (value) => {
    editor.value?.setEditable(!value)
  },
)

function setParagraph(): void {
  editor.value?.chain().focus().setParagraph().run()
}

function toggleHeading(level: 2 | 3): void {
  editor.value?.chain().focus().toggleHeading({ level }).run()
}

function toggleBold(): void {
  editor.value?.chain().focus().toggleBold().run()
}

function toggleItalic(): void {
  editor.value?.chain().focus().toggleItalic().run()
}

function toggleStrike(): void {
  editor.value?.chain().focus().toggleStrike().run()
}

function toggleBlockquote(): void {
  editor.value?.chain().focus().toggleBlockquote().run()
}

function toggleBulletList(): void {
  editor.value?.chain().focus().toggleBulletList().run()
}

function toggleOrderedList(): void {
  editor.value?.chain().focus().toggleOrderedList().run()
}

function toggleCodeBlock(): void {
  editor.value?.chain().focus().toggleCodeBlock().run()
}

function insertHorizontalRule(): void {
  editor.value?.chain().focus().setHorizontalRule().run()
}

function undo(): void {
  editor.value?.chain().focus().undo().run()
}

function redo(): void {
  editor.value?.chain().focus().redo().run()
}

onBeforeUnmount(() => {
  editor.value?.destroy()
})

defineExpose({ editor })
</script>
