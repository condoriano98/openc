// OpenC composer state (thinking, response style, deep research).
// Kept separate from upstream stores to keep upstream merges easy.
import { writable, get } from 'svelte/store';

export type OpenCStyle = { id: string; name: string; prompt: string };

export type OpenCComposerState = {
	thinking: boolean;
	thinkingBudget: number; // 0 = provider default
	style: string; // preset id or custom style id
	deepResearch: boolean;
};

export const STYLE_PRESETS: OpenCStyle[] = [
	{ id: 'normal', name: 'Normal', prompt: '' },
	{ id: 'concise', name: 'Concise', prompt: '' },
	{ id: 'explanatory', name: 'Explanatory', prompt: '' },
	{ id: 'formal', name: 'Formal', prompt: '' }
];

const STORAGE_KEY = 'openc.composer';
const DEFAULT_STATE: OpenCComposerState = {
	thinking: false,
	thinkingBudget: 0,
	style: 'normal',
	deepResearch: false
};

const load = (): OpenCComposerState => {
	try {
		const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
		if (raw) return { ...DEFAULT_STATE, ...JSON.parse(raw), deepResearch: false };
	} catch {
		// ignore unreadable storage
	}
	return { ...DEFAULT_STATE };
};

export const opencComposer = writable<OpenCComposerState>(load());

opencComposer.subscribe((value) => {
	try {
		if (typeof localStorage !== 'undefined') {
			// Deep research is a per-message choice; don't persist it.
			localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...value, deepResearch: false }));
		}
	} catch {
		// ignore unavailable storage
	}
});

export const isDashScopeModel = (model: any): boolean =>
	!!model && (model.provider === 'dashscope' || model?.info?.meta?.openc_provider === 'dashscope');

/** Extra `features` sent with each chat request. */
export const getOpenCFeatures = (customStyles: OpenCStyle[] = []): Record<string, unknown> => {
	const state = get(opencComposer);
	const features: Record<string, unknown> = {};

	if (state.thinking) {
		features.thinking = true;
		if (state.thinkingBudget > 0) features.thinking_budget = state.thinkingBudget;
	}

	if (state.style && state.style !== 'normal') {
		const custom = customStyles.find((s) => s.id === state.style);
		if (custom) {
			features.style = 'custom';
			features.style_prompt = custom.prompt;
		} else if (STYLE_PRESETS.some((s) => s.id === state.style)) {
			features.style = state.style;
		}
	}

	if (state.deepResearch) features.deep_research = true;

	return features;
};
