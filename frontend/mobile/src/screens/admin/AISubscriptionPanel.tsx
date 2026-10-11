import { useCallback, useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import {
  cancelLLMOauth,
  clearLLMApiKey,
  getLLMOauthStatus,
  listLLMModels,
  logoutLLMOauth,
  saveLLMApiKey,
  setLLMOauthAuth,
  startLLMOauth,
  type LLMOauthStatus,
  type LLMProviderChoice,
} from "../../api/admin";
import { PrimaryButton } from "../../components/PrimaryButton";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import { colors, radius, spacing } from "../../theme/theme";
import { getErrorMessage } from "../../utils/errors";

const FALLBACK_PROVIDERS: LLMProviderChoice[] = [
  { id: "qwen", label: "Qwen" },
  { id: "openai", label: "OpenAI" },
  { id: "claude", label: "Claude" },
  { id: "kimi", label: "Kimi" },
  { id: "kimi-code", label: "Kimi Code" },
  { id: "deepseek", label: "DeepSeek" },
  { id: "grok", label: "Grok" },
  { id: "custom", label: "Custom" },
];

function keySourceLabel(status: LLMOauthStatus | null) {
  const source = status?.key.source;
  if (source === "admin") {
    return "Saved in the admin dashboard";
  }
  if (source === "env") {
    return "Loaded from .env";
  }
  return "Not configured";
}

function activeLabel(status: LLMOauthStatus | null) {
  if (status?.auth === "chatgpt") {
    return "ChatGPT Plus / Pro";
  }
  if (status?.auth === "grok") {
    return "Grok SuperGrok / X Premium+";
  }
  return "API key";
}

export function AISubscriptionPanel() {
  const [status, setStatus] = useState<LLMOauthStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [acting, setActing] = useState("");
  const [formHydrated, setFormHydrated] = useState(false);
  const [provider, setProvider] = useState("qwen");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [keyModels, setKeyModels] = useState<string[]>([]);
  const [chatgptModels, setChatgptModels] = useState<string[]>([]);
  const [grokModels, setGrokModels] = useState<string[]>([]);
  const [chatgptModel, setChatgptModel] = useState("");
  const [grokModel, setGrokModel] = useState("");

  const loadStatus = useCallback(async () => {
    try {
      const next = await getLLMOauthStatus();
      if (!next) {
        return;
      }
      setStatus(next);
      if (!formHydrated) {
        setProvider(next.key.provider || "qwen");
        if (next.key.source === "admin") {
          setModel(next.key.model);
          setBaseUrl(next.key.base_url);
        }
        setChatgptModel(next.chatgpt.model || "");
        setGrokModel(next.grok.model || "");
        setFormHydrated(true);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    }
  }, [formHydrated]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const pending = Boolean(status?.chatgpt.pending || status?.grok.pending);

  useEffect(() => {
    if (!pending) {
      return;
    }
    const timer = setInterval(() => {
      void loadStatus();
    }, 2000);
    return () => clearInterval(timer);
  }, [loadStatus, pending]);

  async function run(label: string, action: () => Promise<LLMOauthStatus | null>) {
    setActing(label);
    setErrorMessage("");
    try {
      const next = await action();
      if (next) {
        setStatus(next);
        setProvider(next.key.provider || "qwen");
        if (next.key.source === "admin") {
          setModel(next.key.model);
          setBaseUrl(next.key.base_url);
        }
        setChatgptModel(next.chatgpt.model || chatgptModel);
        setGrokModel(next.grok.model || grokModel);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setActing("");
    }
  }

  async function refreshKeyModels() {
    setActing("models-key");
    setErrorMessage("");
    try {
      const listed = await listLLMModels({
        source: "key",
        provider,
        api_key: apiKey.trim(),
        base_url: baseUrl.trim(),
      });
      if (!listed) {
        return;
      }
      setKeyModels(listed.models);
      if (!model && listed.default) {
        setModel(listed.default);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setActing("");
    }
  }

  async function refreshSubscriptionModels(source: "chatgpt" | "grok") {
    setActing(`models-${source}`);
    setErrorMessage("");
    try {
      const listed = await listLLMModels({ source });
      if (!listed) {
        return;
      }
      if (source === "chatgpt") {
        setChatgptModels(listed.models);
        if (!chatgptModel && listed.default) {
          setChatgptModel(listed.default);
        }
      } else {
        setGrokModels(listed.models);
        if (!grokModel && listed.default) {
          setGrokModel(listed.default);
        }
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setActing("");
    }
  }

  const busy = Boolean(acting);
  const providers = status?.providers?.length ? status.providers : FALLBACK_PROVIDERS;
  const canSaveKey = Boolean(apiKey.trim() || status?.key.configured);

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Customer AI</Text>
      <Text style={styles.active}>Active: {activeLabel(status)}</Text>
      {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

      <View style={styles.card}>
        <Text style={styles.cardTitle}>API key</Text>
        <Text style={styles.cardBody}>
          {keySourceLabel(status)}
          {status?.key.api_key_preview
            ? ` (${status.key.api_key_preview})`
            : ""}
          . Pick a vendor, paste the key, then load the official model list.
          Review embeddings stay on TEI / EMBEDDING_*.
        </Text>
        <View style={styles.providerRow}>
          {providers.map((item) => {
            const selected = provider === item.id;
            return (
              <Pressable
                key={item.id}
                accessibilityRole="button"
                disabled={busy}
                onPress={() => {
                  setProvider(item.id);
                  setKeyModels([]);
                }}
                style={[styles.chip, selected ? styles.chipSelected : null]}
              >
                <Text style={[styles.chipLabel, selected ? styles.chipLabelSelected : null]}>
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <TextField
          autoCapitalize="none"
          label="API key"
          onChangeText={setApiKey}
          placeholder={
            status?.key.api_key_preview
              ? `Saved ${status.key.api_key_preview}`
              : "Vendor API key"
          }
          secureTextEntry
          value={apiKey}
        />
        {provider === "custom" ? (
          <TextField
            autoCapitalize="none"
            label="Base URL"
            onChangeText={setBaseUrl}
            placeholder="https://api.example.com/v1"
            value={baseUrl}
          />
        ) : null}
        <ModelPicker
          models={keyModels}
          onSelect={setModel}
          selected={model}
        />
        <View style={styles.actions}>
          <SecondaryButton
            disabled={busy}
            label="Load official models"
            onPress={() => void refreshKeyModels()}
          />
          <PrimaryButton
            disabled={busy || !canSaveKey}
            isLoading={acting === "key-save"}
            label="Save and use"
            onPress={() =>
              void run("key-save", async () => {
                const next = await saveLLMApiKey({
                  provider,
                  api_key: apiKey.trim(),
                  base_url: baseUrl.trim(),
                  model: model.trim(),
                });
                setApiKey("");
                return next;
              })
            }
          />
          {status?.key.source === "admin" ? (
            <SecondaryButton
              disabled={busy}
              label="Clear saved key"
              onPress={() => void run("key-clear", () => clearLLMApiKey())}
            />
          ) : null}
          {status?.key.configured && status.auth !== "key" ? (
            <SecondaryButton
              disabled={busy}
              label="Use this API key"
              onPress={() => void run("key", () => setLLMOauthAuth("key"))}
            />
          ) : null}
        </View>
      </View>

      <ProviderCard
        acting={acting}
        busy={busy}
        model={chatgptModel}
        models={chatgptModels}
        onCancel={() => void run("chatgpt-cancel", () => cancelLLMOauth("chatgpt"))}
        onLoadModels={() => void refreshSubscriptionModels("chatgpt")}
        onLogout={() => void run("chatgpt-logout", () => logoutLLMOauth("chatgpt"))}
        onSelectModel={setChatgptModel}
        onStart={() => void run("chatgpt-start", () => startLLMOauth("chatgpt"))}
        onUse={() =>
          void run("chatgpt-use", () => setLLMOauthAuth("chatgpt", chatgptModel))
        }
        provider={status?.chatgpt}
        title="ChatGPT Plus / Pro"
      />

      <ProviderCard
        acting={acting}
        busy={busy}
        model={grokModel}
        models={grokModels}
        onCancel={() => void run("grok-cancel", () => cancelLLMOauth("grok"))}
        onLoadModels={() => void refreshSubscriptionModels("grok")}
        onLogout={() => void run("grok-logout", () => logoutLLMOauth("grok"))}
        onSelectModel={setGrokModel}
        onStart={() => void run("grok-start", () => startLLMOauth("grok"))}
        onUse={() => void run("grok-use", () => setLLMOauthAuth("grok", grokModel))}
        provider={status?.grok}
        title="Grok SuperGrok / X Premium+"
      />
    </View>
  );
}

function ModelPicker({
  models,
  onSelect,
  selected,
}: {
  models: string[];
  onSelect: (value: string) => void;
  selected: string;
}) {
  if (models.length === 0) {
    return selected ? (
      <Text style={styles.cardBody}>Selected model: {selected}</Text>
    ) : null;
  }
  return (
    <View style={styles.modelBlock}>
      <Text style={styles.modelLabel}>Official models</Text>
      <View style={styles.providerRow}>
        {models.map((item) => {
          const isSelected = selected === item;
          return (
            <Pressable
              key={item}
              accessibilityRole="button"
              onPress={() => onSelect(item)}
              style={[styles.chip, isSelected ? styles.chipSelected : null]}
            >
              <Text style={[styles.chipLabel, isSelected ? styles.chipLabelSelected : null]}>
                {item}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ProviderCard({
  acting,
  busy,
  model,
  models,
  onCancel,
  onLoadModels,
  onLogout,
  onSelectModel,
  onStart,
  onUse,
  provider,
  title,
}: {
  acting: string;
  busy: boolean;
  model: string;
  models: string[];
  onCancel: () => void;
  onLoadModels: () => void;
  onLogout: () => void;
  onSelectModel: (value: string) => void;
  onStart: () => void;
  onUse: () => void;
  provider?: LLMOauthStatus["chatgpt"];
  title: string;
}) {
  const pending = Boolean(provider?.pending);
  const connected = Boolean(provider?.connected);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardBody}>
        {connected ? "Signed in" : pending ? "Waiting for approval" : "Not signed in"}
        {connected && model ? ` · ${model}` : ""}
      </Text>
      {provider?.user_code ? (
        <Text style={styles.code}>{provider.user_code}</Text>
      ) : null}
      {provider?.url ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => void Linking.openURL(provider.url || "")}
        >
          <Text style={styles.link}>{provider.url}</Text>
        </Pressable>
      ) : null}
      {provider?.error ? <Text style={styles.errorText}>{provider.error}</Text> : null}
      {connected ? (
        <>
          <ModelPicker models={models} onSelect={onSelectModel} selected={model} />
          <SecondaryButton
            disabled={busy}
            label="Load official models"
            onPress={onLoadModels}
          />
        </>
      ) : null}
      <View style={styles.actions}>
        {pending ? (
          <SecondaryButton disabled={busy} label="Cancel" onPress={onCancel} />
        ) : connected ? (
          <>
            <PrimaryButton
              disabled={busy}
              isLoading={acting.endsWith("-use")}
              label="Use this subscription"
              onPress={onUse}
            />
            <SecondaryButton disabled={busy} label="Sign out" onPress={onLogout} />
          </>
        ) : (
          <PrimaryButton
            disabled={busy}
            isLoading={acting.endsWith("-start")}
            label="Sign in"
            onPress={onStart}
          />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "800",
  },
  active: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  card: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
  },
  cardBody: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  modelBlock: {
    gap: spacing.sm,
  },
  modelLabel: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  providerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  chipSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.background,
  },
  chipLabel: {
    color: colors.mutedText,
    fontSize: 14,
    fontWeight: "600",
  },
  chipLabelSelected: {
    color: colors.primary,
  },
  code: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: 2,
  },
  link: {
    color: colors.primary,
    fontSize: 14,
    lineHeight: 20,
  },
  errorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
});
