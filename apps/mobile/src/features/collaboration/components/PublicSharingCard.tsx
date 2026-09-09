import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { Globe, RefreshCw, Link as LinkIcon, Check, Copy } from "lucide-react-native";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";

interface PublicSharingCardProps {
  isPublic: boolean;
  shareToken: string | null;
  onToggle: (enable: boolean) => Promise<void>;
  onRotate: () => Promise<void>;
  isMutating?: boolean;
}

export const PublicSharingCard: React.FC<PublicSharingCardProps> = ({
  isPublic,
  shareToken,
  onToggle,
  onRotate,
  isMutating = false,
}) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    if (!shareToken) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleRotateConfirm = () => {
    Alert.alert(
      "Rotate Share Link",
      "Generating a new link will immediately invalidate the existing link. Anyone with the old link will lose access.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Rotate Link",
          style: "destructive",
          onPress: () => onRotate(),
        },
      ]
    );
  };

  const handleToggleConfirm = () => {
    if (isPublic) {
      Alert.alert(
        "Disable Public Sharing",
        "The public link will be deactivated and no longer accessible to anyone without an account.",
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Disable",
            style: "destructive",
            onPress: () => onToggle(false),
          },
        ]
      );
    } else {
      onToggle(true);
    }
  };

  return (
    <Card className="p-5 bg-slate-900 border border-slate-800 mb-6">
      <View className="flex-row items-center justify-between mb-3">
        <View className="flex-row items-center flex-1 mr-2">
          <View
            className={`w-9 h-9 rounded-xl items-center justify-center mr-3 ${
              isPublic
                ? "bg-emerald-500/10 border border-emerald-500/20"
                : "bg-slate-800 border border-slate-700"
            }`}
          >
            <Globe size={18} color={isPublic ? "#10b981" : "#94a3b8"} />
          </View>
          <View>
            <Text className="text-white text-sm font-bold">Public Sharing</Text>
            <Text className="text-slate-400 text-xs">
              {isPublic ? "Active • Public link enabled" : "Off • Trip is private"}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          onPress={handleToggleConfirm}
          disabled={isMutating}
          className={`px-3 py-1.5 rounded-lg border ${
            isPublic
              ? "bg-rose-950/40 border-rose-800/40 active:bg-rose-900/40"
              : "bg-brand-600 border-brand-500 active:bg-brand-700"
          }`}
        >
          <Text
            className={`text-xs font-semibold ${
              isPublic ? "text-rose-300" : "text-white"
            }`}
          >
            {isPublic ? "Disable" : "Enable"}
          </Text>
        </TouchableOpacity>
      </View>

      <Text className="text-slate-400 text-xs leading-4 mb-3">
        {isPublic
          ? "Anyone with the link below can view this trip without signing in. Public viewers cannot edit trip details, itinerary, or budget."
          : "Allow anyone with a secure public link to view this trip in read-only mode."}
      </Text>

      {isPublic && shareToken && (
        <View className="bg-slate-950 border border-slate-800 rounded-xl p-3 mt-1">
          <View className="flex-row items-center justify-between mb-2">
            <View className="flex-row items-center flex-1 mr-2">
              <LinkIcon size={14} color="#818cf8" />
              <Text
                className="text-indigo-400 text-xs font-mono ml-2 flex-1"
                numberOfLines={1}
              >
                .../public/{shareToken}
              </Text>
            </View>

            <TouchableOpacity
              onPress={handleCopy}
              className="flex-row items-center px-2 py-1 rounded bg-slate-800 border border-slate-700"
            >
              {copied ? (
                <>
                  <Check size={12} color="#10b981" />
                  <Text className="text-emerald-400 text-[11px] font-semibold ml-1">
                    Copied
                  </Text>
                </>
              ) : (
                <>
                  <Copy size={12} color="#94a3b8" />
                  <Text className="text-slate-300 text-[11px] font-semibold ml-1">
                    Copy
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            onPress={handleRotateConfirm}
            disabled={isMutating}
            className="flex-row items-center justify-center pt-2 border-t border-slate-800/80"
          >
            <RefreshCw size={12} color="#94a3b8" />
            <Text className="text-slate-400 text-[11px] font-medium ml-1.5">
              Rotate link (resets access)
            </Text>
          </TouchableOpacity>
        </View>
      )}
    </Card>
  );
};
