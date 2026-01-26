import { SunMoon } from "lucide-react";
import { useEffect, useState } from "react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

type ThemeToggleProps = {
	className?: string;
	label?: string;
};

const STORAGE_KEY = "amr-theme";

function applyTheme(theme: Theme) {
	const root = document.documentElement;
	if (theme === "dark") {
		root.classList.add("dark");
	} else {
		root.classList.remove("dark");
	}
	try {
		localStorage.setItem(STORAGE_KEY, theme);
	} catch {
		// ignore
	}
}

function getInitialTheme(): Theme {
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored === "light" || stored === "dark") return stored;
	} catch {
		// ignore
	}
	return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export default function ThemeToggle({
	className,
	label = "Theme",
}: ThemeToggleProps) {
	const [theme, setTheme] = useState<Theme>("dark");

	useEffect(() => {
		const initial = getInitialTheme();
		setTheme(initial);
		applyTheme(initial);
	}, []);

	return (
		<div
			className={cn(
				"flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400",
				className,
			)}
		>
			<SunMoon className="h-4 w-4" />
			<span>{label}</span>
			<Switch
				checked={theme === "dark"}
				onCheckedChange={(checked) => {
					const next = checked ? "dark" : "light";
					setTheme(next);
					applyTheme(next);
				}}
			/>
		</div>
	);
}
