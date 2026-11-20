<script lang="ts">
	// OpenC Canvas: edit an artifact by hand, or select part of it and ask the
	// AI to change it (inspired by ChatGPT Canvas). AI edits are sent as a chat
	// message, so the reply becomes the artifact's next version.
	import { createEventDispatcher, getContext } from 'svelte';
	import { getChatContext } from '$lib/components/chat/context';

	const i18n: any = getContext('i18n');
	const dispatch = createEventDispatcher<{ change: string; done: void }>();
	const chat = getChatContext();

	export let content = '';
	export let type: 'iframe' | 'svg' | string = 'iframe';

	let textarea: HTMLTextAreaElement;
	let instruction = '';
	let selectedText = '';

	const lang = () => (type === 'svg' ? 'svg' : 'html');

	const updateSelection = () => {
		if (!textarea) return;
		const { selectionStart, selectionEnd } = textarea;
		selectedText = selectionEnd > selectionStart ? content.slice(selectionStart, selectionEnd) : '';
	};

	export const buildEditPrompt = (doc: string, change: string, selection: string, language: string) => {
		const scope = selection
			? `Only change this part of the file (keep everything else identical):\n\`\`\`${language}\n${selection}\n\`\`\`\n\n`
			: '';
		return (
			`Edit the ${language.toUpperCase()} artifact below.\n\n${scope}` +
			`Requested change: ${change}\n\n` +
			`Reply with the complete updated file in a single \`\`\`${language} code block and no other code blocks.\n\n` +
			`Current file:\n\`\`\`${language}\n${doc}\n\`\`\``
		);
	};

	const askAI = () => {
		const change = instruction.trim();
		if (!change || !chat.submitPrompt) return;
		chat.submitPrompt(buildEditPrompt(content, change, selectedText, lang()));
		instruction = '';
		dispatch('done');
	};
</script>

<div class="flex h-full w-full flex-col" data-openc="canvas-editor">
	<textarea
		bind:this={textarea}
		class="min-h-0 flex-1 w-full resize-none bg-white dark:bg-gray-850 p-3 font-mono text-xs leading-relaxed text-gray-800 dark:text-gray-100 outline-hidden"
		spellcheck="false"
		aria-label={$i18n.t('Artifact source')}
		value={content}
		on:input={(e) => {
			content = e.currentTarget.value;
			dispatch('change', content);
		}}
		on:select={updateSelection}
		on:keyup={updateSelection}
		on:mouseup={updateSelection}
	/>

	{#if chat.submitPrompt}
		<form
			class="shrink-0 flex flex-col gap-1 border-t border-gray-100 dark:border-gray-800 p-2"
			on:submit|preventDefault={askAI}
		>
			<div class="text-[0.7rem] text-gray-400 dark:text-gray-500 truncate">
				{#if selectedText}
					{$i18n.t('Editing selection')} ({selectedText.length}
					{$i18n.t('chars')})
				{:else}
					{$i18n.t('Select code to edit just that part, or describe a change to the whole file')}
				{/if}
			</div>
			<div class="flex gap-1">
				<input
					class="flex-1 rounded-lg bg-gray-50 dark:bg-gray-800 px-2 py-1 text-sm outline-hidden"
					placeholder={$i18n.t('Ask AI to change this…')}
					bind:value={instruction}
				/>
				<button
					type="submit"
					class="rounded-lg bg-black px-2.5 py-1 text-xs text-white disabled:opacity-40 dark:bg-white dark:text-black"
					disabled={!instruction.trim()}>{$i18n.t('Ask AI')}</button
				>
			</div>
		</form>
	{/if}
</div>
