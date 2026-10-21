import sys
from PySide6.QtWidgets import QApplication
from pet_window import PetWindow
from input_listener import InputListener


def main():
    # QApplication 是所有 Qt 程序的基础，接收命令行参数
    app = QApplication(sys.argv)
    # 关闭最后一个窗口时不退出程序（因为有隐藏功能）
    app.setQuitOnLastWindowClosed(False)

    # 创建桌宠
    pet = PetWindow()

    # 创建并启动键盘鼠标监听器
    listener = InputListener()
    # 【核心】把监听器的信号，连接到桌宠的槽函数上
    listener.mouse_moved.connect(pet.on_mouse_moved)
    listener.key_pressed.connect(pet.on_key_pressed)
    listener.start()

    pet.show()

    # app.exec() 启动事件循环（死循环监听事件），程序会卡在这里
    code = app.exec()

    # 退出时清理监听器
    listener.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
