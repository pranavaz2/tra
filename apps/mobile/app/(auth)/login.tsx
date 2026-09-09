import React, { useState } from "react";
import {
  View,
  Text,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Link, useRouter } from "expo-router";
import { Compass, Sparkles } from "lucide-react-native";
import { useAuth } from "@/features/auth/context/auth-context";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { TravixApiError } from "@/core/api/client";

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});

  const validate = (): boolean => {
    const errors: { email?: string; password?: string } = {};

    if (!email.trim()) {
      errors.email = "Email is required";
    } else if (!email.includes("@") || !email.includes(".")) {
      errors.email = "Please enter a valid email address";
    }

    if (!password) {
      errors.password = "Password is required";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleLogin = async () => {
    setErrorMessage(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await login({
        email: email.trim(),
        password,
        device_info: {
          platform: Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "web",
          device_name: `${Platform.OS.toUpperCase()} Device`,
        },
      });
      // AuthGate will redirect to tabs automatically
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        if (err.errorCode === "AUTH_INVALID_CREDENTIALS") {
          setErrorMessage("Incorrect email or password. Please try again.");
        } else if (err.errorCode === "AUTH_ACCOUNT_LOCKED") {
          setErrorMessage("Account temporarily locked due to failed attempts. Try again later.");
        } else {
          setErrorMessage(err.message || "Failed to log in.");
        }
      } else {
        setErrorMessage("Network error. Please check your connection and try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-slate-950">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1"
      >
        <ScrollView
          contentContainerStyle={{ flexGrow: 1 }}
          keyboardShouldPersistTaps="handled"
          className="px-6 py-8"
        >
          {/* Header & Logo */}
          <View className="items-center mt-6 mb-10">
            <View className="w-14 h-14 rounded-2xl bg-brand-600/20 border border-brand-500/30 items-center justify-center mb-4">
              <Compass size={32} color="#6366f1" />
            </View>
            <Text className="text-3xl font-bold text-white tracking-tight">Travix AI</Text>
            <View className="flex-row items-center mt-2">
              <Sparkles size={14} color="#38bdf8" />
              <Text className="text-slate-400 text-sm ml-1.5 font-medium">
                Intelligent Travel Planning
              </Text>
            </View>
          </View>

          {/* Form Box */}
          <View className="bg-slate-900/60 border border-slate-800/80 rounded-3xl p-6 shadow-xl mb-6">
            <Text className="text-xl font-bold text-white mb-2">Welcome back</Text>
            <Text className="text-slate-400 text-sm mb-6">
              Sign in to manage and view your trips
            </Text>

            {errorMessage && (
              <ErrorMessage message={errorMessage} className="mb-5" />
            )}

            <Input
              label="Email address"
              placeholder="you@example.com"
              keyboardType="email-address"
              autoComplete="email"
              value={email}
              onChangeText={(text) => {
                setEmail(text);
                if (fieldErrors.email) setFieldErrors((p) => ({ ...p, email: undefined }));
              }}
              error={fieldErrors.email}
            />

            <Input
              label="Password"
              placeholder="••••••••••••"
              isPassword
              value={password}
              onChangeText={(text) => {
                setPassword(text);
                if (fieldErrors.password) setFieldErrors((p) => ({ ...p, password: undefined }));
              }}
              error={fieldErrors.password}
            />

            <Button
              label="Sign In"
              variant="primary"
              size="lg"
              className="mt-2"
              onPress={handleLogin}
              isLoading={isSubmitting}
            />
          </View>

          {/* Footer Register Link */}
          <View className="flex-row items-center justify-center mt-auto pb-4">
            <Text className="text-slate-400 text-sm">Don't have an account? </Text>
            <Link href="/(auth)/register" asChild>
              <TouchableOpacity>
                <Text className="text-brand-400 font-semibold text-sm">Create one</Text>
              </TouchableOpacity>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
