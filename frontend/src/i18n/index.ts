import zh from './zh';
import en from './en';

export type Locale = 'zh' | 'en';
export type Messages = typeof zh;

export const locales: Record<Locale, Messages> = { zh, en };
