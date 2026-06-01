import { MessageCircle, Package, Sparkles, Store } from 'lucide-react'
import type React from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const guideSections = [
  {
    id: 'chat',
    label: 'AI 对话',
    icon: MessageCircle,
    title: '智能对话功能',
    description: '支持多模型切换，可关联技能包增强回答质量',
    steps: [
      { title: '新建对话', content: '点击侧栏顶部的「新建对话」按钮，或在输入框中直接输入消息开始新对话。' },
      { title: '选择模型', content: '在输入框底部的工具栏中，点击模型名称可切换不同的 AI 模型。' },
      { title: '加载技能包', content: '点击「Load Skill Pack...」按钮选择技能包，AI 会根据技能包中的知识回答问题。' },
      { title: '使用工具', content: '点击工具栏中的工具图标可启用/禁用内置工具，增强 AI 的能力。' },
    ],
  },
  {
    id: 'skills',
    label: '技能提取',
    icon: Sparkles,
    title: '书籍技能提取',
    description: '上传 EPUB 电子书，自动解析并生成结构化技能包',
    steps: [
      { title: '上传书籍', content: '进入「我的技能」页面，点击上传按钮选择 EPUB 格式的电子书文件。' },
      { title: '等待处理', content: '系统会自动解析书籍内容，经过概览分析、深度提取、验证筛选等步骤生成技能包。' },
      { title: '查看结果', content: '处理完成后，可在「我的技能」页面查看生成的技能包，包含多个结构化的技能模块。' },
      { title: '下载归档', content: '点击技能包的下载按钮，可将技能包打包为 ZIP 文件下载保存。' },
    ],
  },
  {
    id: 'manage',
    label: '技能管理',
    icon: Package,
    title: '技能包管理',
    description: '管理你的技能包，控制可见性与分享',
    steps: [
      { title: '查看技能包', content: '在「我的技能」页面，可以看到所有已创建的技能包列表。' },
      { title: '设置可见性', content: '点击技能包的可见性按钮，可在「私有」和「公开」之间切换。公开的技能包会出现在广场中。' },
      { title: '删除技能包', content: '点击删除按钮可移除不需要的技能包，此操作不可撤销。' },
      { title: '关联对话', content: '在对话中加载技能包后，AI 会自动使用技能包中的知识来回答相关问题。' },
    ],
  },
  {
    id: 'plaza',
    label: '技能广场',
    icon: Store,
    title: '技能广场',
    description: '浏览和复制其他用户分享的公开技能包',
    steps: [
      { title: '浏览广场', content: '进入「技能广场」页面，可以看到所有用户分享的公开技能包。' },
      { title: '复制技能包', content: '点击「复制到我的库」按钮，可将公开技能包复制到你的个人技能库中。' },
      { title: '使用技能包', content: '复制后的技能包会出现在你的技能列表中，可在对话中加载使用。' },
      { title: '分享你的技能', content: '将你的技能包设置为公开状态，其他用户就能在广场中看到并复制你的技能包。' },
    ],
  },
]

export function GuideDialog({ children }: { children: React.ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh]">
        <DialogHeader>
          <DialogTitle className="text-xl">Skill Chat 功能指南</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="chat" className="w-full">
          <TabsList className="w-full justify-start mb-4">
            {guideSections.map((section) => (
              <TabsTrigger key={section.id} value={section.id} className="gap-1.5">
                <section.icon className="size-3.5" />
                {section.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {guideSections.map((section) => (
            <TabsContent key={section.id} value={section.id}>
              <ScrollArea className="h-[60vh]">
                <div className="space-y-4 pr-4">
                  <div className="space-y-2">
                    <h3 className="text-lg font-semibold">{section.title}</h3>
                    <p className="text-sm text-muted-foreground">{section.description}</p>
                  </div>
                  <div className="grid gap-3">
                    {section.steps.map((step, index) => (
                      <Card key={index} className="border-border/50">
                        <CardHeader className="px-3 py-2">
                          <CardTitle className="text-sm font-medium flex items-center gap-2">
                            <span className="flex items-center justify-center size-5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                              {index + 1}
                            </span>
                            {step.title}
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="px-3 pb-2 pt-0">
                          <p className="text-sm text-muted-foreground leading-relaxed">{step.content}</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>
          ))}
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
