<script lang="ts">
	// OpenC composer pills: Thinking (Qwen), Deep Research, and Response Style.
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { config, settings, user } from '$lib/stores';
	import { updateUserSettings } from '$lib/apis/users';
	import { getChatContext } from '$lib/components/chat/context';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import DropdownMenu from '$lib/components/common/DropdownMenu.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import LightBulb from '$lib/components/icons/LightBulb.svelte';
	import BookOpen from '$lib/components/icons/BookOpen.svelte';
	import PenAlt from '$lib/components/icons/PenAlt.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		opencComposer,
		STYLE_PRESETS,
		isDashScopeModel,
		type OpenCStyle
	} from '$lib/openc';

	const i18n: any = getContext('i18n');
	const { models } = getChatContext();

	export let selectedModelIds: string[] = [];

	$: selected = selectedModelIds
		.map((id) => $models.find((m: any) => m.id === id))
		.filter(Boolean);
	$: showThinking = selected.some((model) => {
		if (isDashScopeModel(model)) return true;
		const baseId = (model as any)?.info?.base_model_id;
		return !!baseId && isDashScopeModel($models.find((m: any) => m.id === baseId));
	});
	$: if (!showThinking && $opencComposer.thinking) opencComposer.update((s) => ({ ...s, thinking: false }));

	$: showResearch =
		!!$config?.features?.enable_web_search &&
		($user?.role === 'admin' || !!$user?.permissions?.features?.web_search);

	$: customStyles = (($settings as any)?.opencStyles ?? []) as OpenCStyle[];
	$: allStyles = [...STYLE_PRESETS, ...customStyles];
	$: activeStyle = allStyles.find((s) => s.id === $opencComposer.style) ?? STYLE_PRESETS[0];

	const BUDGETS = [0, 4096, 16384, 38912];

	let showStyleMenu = false;
	let creating = false;
	let newName = '';
	let newPrompt = '';

	const pillClass = (active: boolean) =>
		`group p-[0.375rem] px-2 flex gap-1 items-center text-xs rounded-full transition-colors duration-300 focus:outline-hidden max-w-full overflow-hidden ${
			active
				? 'text-sky-500 dark:text-sky-300 bg-sky-50 hover:bg-sky-100 dark:bg-sky-400/10 dark:hover:bg-sky-600/10 border border-sky-200/40 dark:border-sky-500/20'
				: 'bg-transparent text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
		}`;

	const saveCustomStyles = async (styles: OpenCStyle[]) => {
		const previous = customStyles;
		settings.set({ ...$settings, opencStyles: styles } as any);
		try {
			await updateUserSettings(localStorage.token, { ui: { opencStyles: styles } });
		} catch (error) {
			settings.set({ ...$settings, opencStyles: previous } as any);
			toast.error(`${error}`);
		}
	};

	const createStyle = async () => {
		const name = newName.trim();
		const prompt = newPrompt.trim();
		if (!name || !prompt) return;
		const style = { id: `custom-${Date.now().toString(36)}`, name, prompt };
		await saveCustomStyles([...customStyles, style]);
		opencComposer.update((s) => ({ ...s, style: style.id }));
		creating = false;
		newName = '';
		newPrompt = '';
	};

	const deleteStyle = async (id: string) => {
		await saveCustomStyles(customStyles.filter((s) => s.id !== id));
		if ($opencComposer.style === id) opencComposer.update((s) => ({ ...s, style: 'normal' }));
	};
</script>

<div class="flex items-center gap-1" data-openc="composer-controls">
	{#if showThinking}
		<Tooltip
			content={$opencComposer.thinking
				? $i18n.t('Thinking on — click to cycle budget, right-click to turn off')
				: $i18n.t('Think before answering (Qwen)')}
			placement="top"
		>
			<button
				type="button"
				data-openc="thinking"
				aria-pressed={$opencComposer.thinking}
				class={pillClass($opencComposer.thinking)}
				on:click|preventDefault={() =>
					opencComposer.update((s) => {
						if (!s.thinking) return { ...s, thinking: true, thinkingBudget: 0 };
						const next = BUDGETS[(BUDGETS.indexOf(s.thinkingBudget) + 1) % BUDGETS.length];
						return next === 0 ? { ...s, thinking: false } : { ...s, thinkingBudget: next };
					})}
				on:contextmenu|preventDefault={() =>
					opencComposer.update((s) => ({ ...s, thinking: false, thinkingBudget: 0 }))}
			>
				<LightBulb className="size-4" strokeWidth="1.75" />
				<span class="hidden sm:inline">
					{$i18n.t('Think')}{$opencComposer.thinking && $opencComposer.thinkingBudget
						? ` · ${Math.round($opencComposer.thinkingBudget / 1024)}k`
						: ''}
				</span>
			</button>
		</Tooltip>
	{/if}

	{#if showResearch}
		<Tooltip content={$i18n.t('Deep Research: multi-step web research with a cited report')} placement="top">
			<button
				type="button"
				data-openc="deep-research"
				aria-pressed={$opencComposer.deepResearch}
				class={pillClass($opencComposer.deepResearch)}
				on:click|preventDefault={() =>
					opencComposer.update((s) => ({ ...s, deepResearch: !s.deepResearch }))}
			>
				<BookOpen className="size-4" />
				<span class="hidden sm:inline">{$i18n.t('Research')}</span>
			</button>
		</Tooltip>
	{/if}

	<Dropdown
		bind:show={showStyleMenu}
		side="top"
		align="start"
		onOpenChange={(open) => {
			if (!open) creating = false;
		}}
	>
		<Tooltip content={$i18n.t('Response style')} placement="top">
			<button
				type="button"
				data-openc="style"
				class={pillClass(activeStyle.id !== 'normal')}
				aria-label={$i18n.t('Response style')}
			>
				<PenAlt className="size-4" />
				{#if activeStyle.id !== 'normal'}
					<span class="hidden sm:inline max-w-24 truncate">{$i18n.t(activeStyle.name)}</span>
				{/if}
			</button>
		</Tooltip>

		<div slot="content">
			<DropdownMenu className="w-64 max-w-[calc(100vw-2rem)] p-1">
				<div class="px-2 pt-1 pb-1 text-xs text-gray-400 dark:text-gray-500">
					{$i18n.t('Response style')}
				</div>
				{#each allStyles as style (style.id)}
					<div
						class="flex items-center rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/60 text-sm"
					>
						<button
							type="button"
							class="flex-1 flex items-center gap-2 px-2 py-1.5 text-left"
							on:click={() => {
								opencComposer.update((s) => ({ ...s, style: style.id }));
								showStyleMenu = false;
							}}
						>
							<span class="flex-1 truncate">{$i18n.t(style.name)}</span>
							{#if $opencComposer.style === style.id}
								<Check className="size-3.5" />
							{/if}
						</button>
						{#if style.id.startsWith('custom-')}
							<button
								type="button"
								class="p-1.5 text-gray-400 hover:text-red-500"
								aria-label={$i18n.t('Delete')}
								on:click|stopPropagation={() => deleteStyle(style.id)}
							>
								<XMark className="size-3.5" />
							</button>
						{/if}
					</div>
				{/each}

				<hr class="my-1 border-gray-100 dark:border-gray-800" />

				{#if creating}
					<form class="flex flex-col gap-1.5 p-1.5" on:submit|preventDefault={createStyle}>
						<input
							class="w-full rounded-lg bg-gray-50 dark:bg-gray-850 px-2 py-1 text-sm outline-hidden"
							placeholder={$i18n.t('Style name')}
							bind:value={newName}
							maxlength="40"
						/>
						<textarea
							class="w-full rounded-lg bg-gray-50 dark:bg-gray-850 px-2 py-1 text-sm outline-hidden resize-none"
							rows="4"
							placeholder={$i18n.t('Describe how the assistant should write…')}
							bind:value={newPrompt}
							maxlength="4000"
						/>
						<div class="flex justify-end gap-1">
							<button
								type="button"
								class="px-2 py-1 text-xs rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => (creating = false)}>{$i18n.t('Cancel')}</button
							>
							<button
								type="submit"
								class="px-2 py-1 text-xs rounded-lg bg-black text-white dark:bg-white dark:text-black disabled:opacity-50"
								disabled={!newName.trim() || !newPrompt.trim()}>{$i18n.t('Save')}</button
							>
						</div>
					</form>
				{:else}
					<button
						type="button"
						class="w-full px-2 py-1.5 text-left text-sm rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/60"
						on:click|stopPropagation={() => (creating = true)}
					>
						+ {$i18n.t('Create style')}
					</button>
				{/if}
			</DropdownMenu>
		</div>
	</Dropdown>
</div>
