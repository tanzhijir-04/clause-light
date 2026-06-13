import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';

interface Step {
  key: string;
  label: string;
}

interface Props {
  steps: Step[];
  currentStep: number; // 1-based
  progress: number; // 0-100
}

export default function StepProgress({ steps, currentStep, progress }: Props) {
  const { colors } = useThemeContext();

  return (
    <View style={styles.container}>
      {/* 步骤节点 */}
      <View style={styles.stepsRow}>
        {steps.map((step, index) => {
          const stepNum = index + 1;
          const isActive = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;

          return (
            <React.Fragment key={step.key}>
              {/* 节点 */}
              <View style={styles.stepNode}>
                <View
                  style={[
                    styles.node,
                    {
                      backgroundColor: isCompleted || isActive ? colors.accent : colors.muted,
                      borderColor: isCompleted || isActive ? colors.accent : colors.border,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.nodeText,
                      { color: isCompleted || isActive ? colors.textInverse : colors.textTertiary },
                    ]}
                  >
                    {isCompleted ? '✓' : stepNum}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.stepLabel,
                    {
                      color: isActive ? colors.accent : isCompleted ? colors.text : colors.textTertiary,
                      fontWeight: isActive ? '600' : '400',
                    },
                  ]}
                >
                  {step.label}
                </Text>
              </View>

              {/* 连接线 */}
              {index < steps.length - 1 && (
                <View style={styles.lineContainer}>
                  <View style={[styles.line, { backgroundColor: colors.border }]} />
                  {isCompleted && (
                    <View style={[styles.lineCompleted, { backgroundColor: colors.accent }]} />
                  )}
                </View>
              )}
            </React.Fragment>
          );
        })}
      </View>

      {/* 进度条 */}
      <View style={[styles.progressTrack, { backgroundColor: colors.muted }]}>
        <View
          style={[
            styles.progressBar,
            { width: `${progress}%`, backgroundColor: colors.accent },
          ]}
        />
      </View>
      <Text style={[styles.progressText, { color: colors.textSecondary }]}>
        {progress}%
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  stepsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'center',
    marginBottom: spacing.xl,
    width: '100%',
  },
  stepNode: {
    alignItems: 'center',
    width: 56,
  },
  node: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.xs,
  },
  nodeText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  stepLabel: {
    fontSize: fontSize.xs,
    textAlign: 'center',
  },
  lineContainer: {
    flex: 1,
    height: 2,
    marginTop: 15,
    marginHorizontal: -4,
    position: 'relative',
  },
  line: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 2,
    borderRadius: 1,
  },
  lineCompleted: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 2,
    borderRadius: 1,
  },
  progressTrack: {
    width: '100%',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  progressBar: {
    height: '100%',
    borderRadius: 3,
  },
  progressText: {
    fontSize: fontSize.xs,
  },
});
