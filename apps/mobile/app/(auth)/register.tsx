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
import { Compass, ShieldCheck } from "lucide-react-native";
import { useAuth } from "@/features/auth/context/auth-context";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { TravixApiError } from "@/core/api/client";

export default function RegisterScreen() {
  const router = useRouter();
  const { register } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const validate = (): boolean => {
    const errors: { email?: string; password?: string; confirmPassword?: string } = {};

    if (!email.trim()) {
      errors.email = "Email is required";
    } else if (!email.includes("@") || !email.includes(".")) {
      errors.email = "Please enter a valid email address";
    }

    if (!password) {
      errors.password = "Password is required";
    } else if (password.length < 12) {
      errors.password = "Password must be at least 12 characters";
    }

    if (password !== confirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleRegister = async () => {
    setErrorMessage(null);
    setInfoMessage(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const result = await register({
        email: email.trim(),
        password,
        device_info: {
          platform: Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "web",
          device_name: `${Platform.OS.toUpperCase()} Device`,
        },
      });

      if (result.requiresVerification) {
        setInfoMessage("Account created! Please check your email to verify before signing in.");
      }
      // If requiresVerification is false, AuthGate will automatically redirect to tabs
    } catch (err: any) {
      if (err instanceof TravixApiError) {
        if (err.errorCode === "AUTH_EMAIL_ALREADY_EXISTS") {
          setFieldErrors((p) => ({ ...p, email: "An account with this email already exists" }));
        } else if (err.errorCode === "AUTH_PASSWORD_TOO_WEAK") {
          setFieldErrors((p) => ({ ...p, password: err.message || "Password is too weak (min 12 characters)" }));
        } else {
          setErrorMessage(err.message || "Registration failed. Please try again.");
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
          <View className="items-center mt-4 mb-8">
            <View className="w-14 h-14 rounded-2xl bg-brand-600/20 border border-brand-500/30 items-center justify-center mb-4">
              <Compass size={32} color="#6366f1" />
            </View>
            <Text className="text-3xl font-bold text-white tracking-tight">Travix AI</Text>
            <Text className="text-slate-400 text-sm mt-1.5 font-medium">
              Create your travel planner account
            </Text>
          </View>

          {/* Form Box */}
          <View className="bg-slate-900/60 border border-slate-800/80 rounded-3xl p-6 shadow-xl mb-6">
            <Text className="text-xl font-bold text-white mb-2">Get started</Text>
            <Text className="text-slate-400 text-sm mb-6">
              Plan intelligent itineraries with real-world places
            </Text>

            {errorMessage && (
              <ErrorMessage message={errorMessage} className="mb-5" />
            )}

            {infoMessage && (
              <View className="bg-brand-950/60 border border-brand-700/60 rounded-xl p-4 mb-5 flex-row items-center">
                <ShieldCheck size={20} color="#818cf8" />
                <Text className="text-brand-200 text-sm ml-2.5 flex-1">{infoMessage}</Text>
              </View>
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
              placeholder="At least 12 characters"
              isPassword
              helperText="Must be at least 12 characters"
              value={password}
              onChangeText={(text) => {
                setPassword(text);
                if (fieldErrors.password) setFieldErrors((p) => ({ ...p, password: undefined }));
              }}
              error={fieldErrors.password}
            />

            <Input
              label="Confirm Password"
              placeholder="Re-enter password"
              isPassword
              value={confirmPassword}
              onChangeText={(text) => {
                setConfirmPassword(text);
                if (fieldErrors.confirmPassword)
                  setFieldErrors((p) => ({ ...p, confirmPassword: undefined }));
              }}
              error={fieldErrors.confirmPassword}
            />

            <Button
              label="Create Account"
              variant="primary"
              size="lg"
              className="mt-2"
              onPress={handleRegister}
              isLoading={isSubmitting}
            />
          </View>

          {/* Footer Login Link */}
          <View className="flex-row items-center justify-center mt-auto pb-4">
            <Text className="text-slate-400 text-sm">Already have an account? </Text>
            <Link href="/(auth)/login" asChild>
              <TouchableOpacity>
                <Text className="text-brand-400 font-semibold text-sm">Sign in</Text>
              </TouchableOpacity>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
