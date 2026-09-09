/**
 * AssistantMessageBubble Component.
 *
 * Renders user vs assistant vs system messages in the trip chat timeline.
 */

import React from "react";
import { View, Text } from "react-native";
import { Bot, User, Sparkles, HelpCircle, AlertCircle } from "lucide-react-native";
import { AssistantUIMessage } from "../hooks/use-assistant";
import { ProposedActionCard } from "./ProposedActionCard";

interface AssistantMessageBubbleProps {
  message: AssistantUIMessage;
  onConfirmAction: (actionId: string) => void;
  onRejectAction: (actionId: string) => void;
  isMutating?: boolean;
  isViewer?: boolean;
}

export const AssistantMessageBubble: React.FC<AssistantMessageBubbleProps> = ({
  message,
  onConfirmAction,
  onRejectAction,
  isMutating = false,
  isViewer = false,
}) => {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <View className="my-2.5 px-4 py-2 bg-slate-900/60 rounded-xl border border-slate-800/80 self-center max-w-[90%]">
        <Text className="text-slate-300 text-xs text-center font-medium">
          {message.content}
        </Text>
      </View>
    );
  }

  return (
    <View
      className={`my-2 flex-row ${
        isUser ? "justify-end" : "justify-start"
      } max-w-full`}
    >
      {!isUser && (
        <View className="w-8 h-8 rounded-full bg-brand-600/20 border border-brand-500/30 items-center justify-center mr-2.5 mt-0.5">
          <Sparkles size={16} color="#818cf8" />
        </View>
      )}

      <View
        className={`max-w-[82%] rounded-2xl p-4 ${
          isUser
            ? "bg-brand-600 text-white rounded-tr-none"
            : "bg-slate-900 border border-slate-800 text-slate-100 rounded-tl-none"
        }`}
      >
        {/* Response category tag for assistant */}
        {!isUser && message.responseType && (
          <View className="flex-row items-center mb-1.5">
            <View className="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700/60">
              <Text className="text-brand-300 text-[10px] font-bold uppercase tracking-wider">
                {message.responseType.replace(/_/g, " ")}
              </Text>
            </View>
          </View>
        )}

        {/* Message text */}
        <Text
          className={`text-sm leading-relaxed ${
            isUser ? "text-white font-medium" : "text-slate-200"
          }`}
        >
          {message.content}
        </Text>

        {/* Proposed Action Card */}
        {!isUser && message.proposedAction && (
          <ProposedActionCard
            action={message.proposedAction}
            onConfirm={onConfirmAction}
            onReject={onRejectAction}
            isMutating={isMutating}
            isViewer={isViewer}
          />
        )}

        {/* Timestamp */}
        <Text
          className={`text-[10px] mt-1.5 self-end ${
            isUser ? "text-brand-200/70" : "text-slate-500"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Text>
      </View>

      {isUser && (
        <View className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 items-center justify-center ml-2.5 mt-0.5">
          <User size={16} color="#cbd5e1" />
        </View>
      )}
    </View>
  );
};
