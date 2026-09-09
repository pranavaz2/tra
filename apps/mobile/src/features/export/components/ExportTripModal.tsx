/**
 * ExportTripModal Component.
 *
 * Provides quick actions to export and share trip as PDF or iCal (.ics).
 */

import React, { useState } from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Share,
} from "react-native";
import {
  Calendar,
  FileText,
  Download,
  Share2,
  X,
  CheckCircle2,
} from "lucide-react-native";
import * as Linking from "expo-linking";
import { exportApi } from "../api/export-api";
import { Button } from "@/shared/components/ui/Button";

interface ExportTripModalProps {
  visible: boolean;
  onClose: () => void;
  tripId: string;
  tripTitle: string;
}

export const ExportTripModal: React.FC<ExportTripModalProps> = ({
  visible,
  onClose,
  tripId,
  tripTitle,
}) => {
  const [isExporting, setIsExporting] = useState(false);

  const handleExportPdf = async () => {
    try {
      setIsExporting(true);
      const url = exportApi.getPdfUrl(tripId);
      await Linking.openURL(url);
      onClose();
    } catch (err: any) {
      Alert.alert("Export Failed", err.message || "Failed to open PDF export.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleExportICal = async () => {
    try {
      setIsExporting(true);
      const url = exportApi.getICalUrl(tripId);
      await Linking.openURL(url);
      onClose();
    } catch (err: any) {
      Alert.alert("Export Failed", err.message || "Failed to open iCalendar export.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View className="flex-1 bg-black/80 justify-center items-center px-5">
        <View className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md p-6 overflow-hidden">
          {/* Header */}
          <View className="flex-row items-center justify-between mb-2">
            <View className="flex-row items-center">
              <View className="w-10 h-10 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 items-center justify-center mr-3">
                <Share2 size={20} color="#818cf8" />
              </View>
              <View>
                <Text className="text-white text-lg font-bold">Export Itinerary</Text>
                <Text className="text-slate-400 text-xs mt-0.5" numberOfLines={1}>
                  {tripTitle}
                </Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={16} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          <Text className="text-slate-300 text-xs my-4 leading-5">
            Download your full travel schedule, reservations, and budget breakdown for offline access or calendar sync.
          </Text>

          {/* Export Options */}
          <View className="space-y-3 mb-6">
            {/* PDF Option */}
            <TouchableOpacity
              onPress={handleExportPdf}
              disabled={isExporting}
              className="flex-row items-center p-4 rounded-2xl bg-slate-800/80 border border-slate-700/80 active:bg-slate-700/80"
            >
              <View className="w-11 h-11 rounded-xl bg-rose-500/10 border border-rose-500/20 items-center justify-center mr-3.5">
                <FileText size={22} color="#f43f5e" />
              </View>
              <View className="flex-1">
                <Text className="text-white text-sm font-semibold">PDF Document</Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  Formatted itinerary with day schedules & budget summary
                </Text>
              </View>
              <Download size={18} color="#94a3b8" />
            </TouchableOpacity>

            {/* iCal Option */}
            <TouchableOpacity
              onPress={handleExportICal}
              disabled={isExporting}
              className="flex-row items-center p-4 rounded-2xl bg-slate-800/80 border border-slate-700/80 active:bg-slate-700/80 mt-3"
            >
              <View className="w-11 h-11 rounded-xl bg-sky-500/10 border border-sky-500/20 items-center justify-center mr-3.5">
                <Calendar size={22} color="#38bdf8" />
              </View>
              <View className="flex-1">
                <Text className="text-white text-sm font-semibold">iCalendar (.ics)</Text>
                <Text className="text-slate-400 text-xs mt-0.5">
                  Sync with Apple Calendar, Google Calendar & Outlook
                </Text>
              </View>
              <Download size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Cancel */}
          <Button
            label="Close"
            variant="outline"
            size="md"
            onPress={onClose}
            className="w-full"
          />
        </View>
      </View>
    </Modal>
  );
};
