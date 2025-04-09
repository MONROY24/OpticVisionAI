import asyncio
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from bleak import BleakClient, BleakScanner, BleakError
import struct

COLOR_FONDO = [0.9, 0.9, 0.9, 1]  # Gris claro
COLOR_TEXTO = [0, 0, 0, 1]  # Negro
COLOR_BOTON_CONECTAR = [0.2, 0.8, 0.2, 1]  # Verde vivo
COLOR_BOTON_RESETEAR = [0.8, 0.2, 0.2, 1]  # Rojo suave
COLOR_BOTON_RECOMENDACION = [0.1, 0.6, 0.9, 1]  # Azul suave
COLOR_TEXTO_RECOMENDACIONES = [1, 1, 1, 1]  # Blanco
COLOR_GRAFICA_TEMP = [0, 0, 0, 1]  # Negro
COLOR_GRAFICA_HUM = [0, 0, 0, 1]  # Negro
COLOR_TITULO = [1, 0, 0]

UUID_SERVICIO = "0000180d-0000-1000-8000-00805f9b34fb"
UUID_TEMP = "00002a6e-0000-1000-8000-00805f9b34fb"
UUID_HUM = "00002a6f-0000-1000-8000-00805f9b34fb"
NOMBRE_DISPOSITIVO_BLE = "EnvSensor"

class ControlPlagas(App):
    def build(self):
        self.cliente = None
        self.datos_temp = []
        self.datos_hum = []
        self.temp_actual = 0
        self.hum_actual = 0
        self.alertas = []

        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        with root.canvas.before:
            Color(*COLOR_FONDO)  
            self.rect = Rectangle(size=root.size, pos=root.pos)
            root.bind(size=self._update_rect, pos=self._update_rect)

        encabezado = Label(text="-MONITOREO DE FRIJOL-", font_size='27sp', bold=True, size_hint_y=None, height=dp(60), color=COLOR_TITULO)
        root.add_widget(encabezado)

        # Botones de ayuda
        botones_ayuda = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint=(1, None), height=dp(50))
        btn_prevencion = Button(text="Guía: Prevención", on_press=self.mostrar_guia_prevencion, background_color=COLOR_BOTON_RECOMENDACION, color=COLOR_TEXTO)
        btn_tratamiento = Button(text="Guía: Tratamiento de contacto", on_press=self.mostrar_guia_tratamiento, background_color=COLOR_BOTON_RECOMENDACION, color=COLOR_TEXTO)
        botones_ayuda.add_widget(btn_prevencion)
        botones_ayuda.add_widget(btn_tratamiento)
        root.add_widget(botones_ayuda)

        self.grafica_temp = Graph(xlabel='Tiempo', ylabel='Temperatura (°C)', 
                                   x_ticks_minor=5, x_ticks_major=25, y_ticks_major=1,
                                   y_grid_label=True, x_grid_label=True, padding=dp(5), 
                                   xmin=0, xmax=100, ymin=-10, ymax=40, 
                                   size_hint=(1, 0.4),
                                   label_options={'color': COLOR_TEXTO, 'bold': True})  
        self.trama_temp = MeshLinePlot(color=COLOR_GRAFICA_TEMP)
        self.grafica_temp.add_plot(self.trama_temp)
        root.add_widget(self.grafica_temp)

        self.grafica_hum = Graph(xlabel='Tiempo', ylabel='Humedad (%)', 
                                   x_ticks_minor=10, x_ticks_major=25, y_ticks_major=10,
                                   y_grid_label=True, x_grid_label=True, padding=dp(5), 
                                   xmin=0, xmax=500, ymin=0, ymax=100,
                                   size_hint=(1, 0.4),
                                   label_options={'color': COLOR_TEXTO, 'bold': True})  
        self.trama_hum = MeshLinePlot(color=COLOR_GRAFICA_HUM)
        self.grafica_hum.add_plot(self.trama_hum)
        root.add_widget(self.grafica_hum)

        
        diseño_valores = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(10))
        self.label_temp = Label(text=f"Temperatura: {self.temp_actual} °C", font_size='18sp', color=COLOR_TEXTO, size_hint_x=None, width=dp(200))
        self.label_hum = Label(text=f"Humedad: {self.hum_actual} %", font_size='18sp', color=COLOR_TEXTO, size_hint_x=None, width=dp(200))
        diseño_valores.add_widget(self.label_temp)
        diseño_valores.add_widget(self.label_hum)
        root.add_widget(diseño_valores)

        self.label_estado = Label(text="Estado: Desconectado", font_size='16sp', color=COLOR_TEXTO, size_hint_y=None, height=dp(40))
        root.add_widget(self.label_estado)

        
        botones_control = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.boton_conectar = Button(text="Conectar", on_press=self.iniciar_hilo_ble, size_hint_x=0.5, background_color=COLOR_BOTON_CONECTAR, color=COLOR_TEXTO)
        self.boton_resetear = Button(text="Resetear", on_press=self.resetear_datos, size_hint_x=0.5, background_color=COLOR_BOTON_RESETEAR, color=COLOR_TEXTO)
        botones_control.add_widget(self.boton_conectar)
        botones_control.add_widget(self.boton_resetear)
        root.add_widget(botones_control)

        pie_pagina = Label(text="© 2024 Humboldt Technology", font_size='12sp', size_hint_y=None, height=dp(30), color=COLOR_TEXTO)
        root.add_widget(pie_pagina)

        return root

    def iniciar_hilo_ble(self, instancia):
        threading.Thread(target=self.ejecutar_bucle_ble, daemon=True).start()

    def ejecutar_bucle_ble(self):
        asyncio.run(self.conectar_ble())

    async def conectar_ble(self):
        try:
            dispositivos = await BleakScanner.discover()
            dispositivo_objetivo = None
            for dispositivo in dispositivos:
                if dispositivo.name == NOMBRE_DISPOSITIVO_BLE:
                    dispositivo_objetivo = dispositivo
                    break

            if not dispositivo_objetivo:
                self.label_estado.text = f"Estado: Dispositivo '{NOMBRE_DISPOSITIVO_BLE}' no encontrado."
                return

            self.cliente = BleakClient(dispositivo_objetivo)
            await self.cliente.connect()
            self.label_estado.text = "Estado: Conectado"

            await self.cliente.start_notify(UUID_TEMP, self.manejador_notificaciones)
            await self.cliente.start_notify(UUID_HUM, self.manejador_notificaciones)

            while self.cliente.is_connected:
                await asyncio.sleep(0.1)
        except BleakError as e:
            self.label_estado.text = f"Estado: Error de conexión: {e}"

    def manejador_notificaciones(self, emisor, datos):
        try:
            if len(datos) == 4:
                valor = struct.unpack('<f', datos)[0]
                if emisor.uuid.lower() == UUID_TEMP.lower():
                    self.datos_temp.append(valor)
                    if len(self.datos_temp) > 100:
                        self.datos_temp.pop(0)
                    Clock.schedule_once(lambda dt: self.actualizar_grafica(self.trama_temp, self.datos_temp))
                    self.temp_actual = valor
                    self.label_temp.text = f"Temperatura: {self.temp_actual:.2f} °C"
                elif emisor.uuid.lower() == UUID_HUM.lower():
                    self.datos_hum.append(valor)
                    if len(self.datos_hum) > 100:
                        self.datos_hum.pop(0)
                    Clock.schedule_once(lambda dt: self.actualizar_grafica(self.trama_hum, self.datos_hum))
                    self.hum_actual = valor
                    self .label_hum.text = f"Humedad: {self.hum_actual:.2f} %"
                self.verificar_alertas()
        except Exception as e:
            print(f"Error en el manejador de notificaciones: {e}")

    def actualizar_grafica(self, trama, datos):
        trama.points = [(i, v) for i, v in enumerate(datos)]

    def verificar_alertas(self):
        self.alertas.clear()

        if self.temp_actual >= 15 and self.temp_actual <= 25 and self.hum_actual >= 85 and self.hum_actual <= 100:
            self.alertas.append("ALERTA: Condiciones ideales para Hongo blanco (Sclerotinia sclerotiorum).")

       
        if self.temp_actual >= 15 and self.temp_actual <= 20 and self.hum_actual >= 80 and self.hum_actual <= 90:
            self.alertas.append("ALERTA: Condiciones ideales para Mildiu (Peronospora manshurica).")

       
        if self.temp_actual >= 20 and self.temp_actual <= 30 and self.hum_actual >= 70 and self.hum_actual <= 85:
            self.alertas.append("ALERTA: Condiciones ideales para Antracnosis (Colletotrichum lindemuthianum).")

      
        if self.temp_actual >= 20 and self.temp_actual <= 28 and self.hum_actual >= 60 and self.hum_actual <= 75:
            self.alertas.append("ALERTA: Condiciones ideales para Pudrición de raíz (Rhizoctonia solani).")

        
        if self.temp_actual >= 20 and self.temp_actual <= 30 and self.hum_actual >= 60 and self.hum_actual <= 80:
            self.alertas.append("ALERTA: Condiciones ideales para Virus del mosaico (Bean common mosaic virus).")

        if self.alertas:
            self.mostrar_alertas()

    def mostrar_alertas(self):
        contenido = BoxLayout(orientation='vertical', padding=dp(10))
        for alerta in self.alertas:
            contenido.add_widget(Label(text=alerta, color=[1, 0, 0, 1], size_hint_y=None, height=dp(30)))

        
        self.popup_alertas = Popup(title="Alertas de Enfermedades", content=ScrollView(contenido), size_hint=(0.8, 0.8))
        self.popup_alertas.open()

    def mostrar_guia_prevencion(self, instance):
        contenido = BoxLayout(orientation='vertical', padding=dp(10), size_hint_y=None)
        contenido.bind(minimum_height=contenido.setter('height'))

        contenido.add_widget(Label(text="Guía de Prevención", font_size='20sp', bold=True, size_hint_y=None, height=dp(30)))
        contenido.add_widget(Label(text="Ingredientes:\n\n "
                                      "- 1 litro de agua\n"
                                      "- 2 cucharadas de aceite de neem\n"
                                      "- 1 diente de ajo\n"
                                      "- 1 cebolla pequeña\n"
                                      "- 1 cucharada de bicarbonato de sodio\n"
                                      "- 1 cucharada de vinagre blanco\n"
                                      "- 1 cucharada de jabón de castilla\n\n"
                                      "Instrucciones:\n\n"
                                      "1. Infusión de ajo y cebolla: Pica el ajo y la cebolla. Hierve en 0.5 litros de agua durante 15 minutos. Deja enfriar y cuela.\n\n"
                                      "2. Mezcla: En un recipiente, combina 0.5 litros de agua, el aceite de neem, el bicarbonato, el vinagre y el jabón de castilla. Añade la infusión de ajo y cebolla.\n\n"
                                      "3. Aplicación: Vierte la mezcla en un rociador y aplica sobre las hojas y tallos de las plantas de frijol. Realiza la aplicación por la mañana o al atardecer.\n\n"
                                      "Notas:\n\n"
                                      "- Repite cada 10-14 días o después de lluvias fuertes.\n"
                                      "- Almacena el sobrante en un lugar fresco y oscuro, agitando bien antes de usar.",
                                      size_hint_y=None, height=dp(400)))

        scroll = ScrollView(size_hint=(0.8, 0.8))
        scroll.add_widget(contenido)

       
        self.popup_prevencion = Popup(title="Guía de Prevención", content=scroll, size_hint=(0.8, 0.8))
        self.popup_prevencion.open()

    def mostrar_guia_tratamiento(self, instance):
        contenido = BoxLayout(orientation='vertical', padding=dp(10), size_hint_y=None)
        contenido.bind(minimum_height=contenido.setter('height'))

        contenido.add_widget(Label(text="Tratamientos para el Contacto con Moho", font_size='20sp', bold=True, size_hint_y=None, height=dp(30)))
        contenido.add_widget(Label(text="Mezcla para Limpiar la Piel tras el Contacto con Moho\n"
                                      "Ingredientes:\n"
                                      "- 1 litro de agua tibia\n"
                                      "- 2 cucharadas de bicarbonato de sodio\n"
                                      "- 1 cucharada de vinagre blanco\n"
                                      "- 1 cucharadita de jabón líquido neutro\n\n"
                                      "Instrucciones:\n"
                                      "1. Preparar la mezcla: Mezcla todos los ingredientes en un recipiente.\n"
                                      "2. Lavar la zona afectada: Lava cuidadosamente la piel con esta mezcla y enjuaga bien.\n"
                                      "3. Secar y observar: Seca la piel con una toalla limpia y observa cualquier reacción.\n\n"
                                      "\nBaño Calmante para Reacciones alérgicas al Moho Blanco\n"
                                      "Ingredientes:\n"
                                      "- 1 taza de avena coloidal (finamente molida)\n"
                                      "- 1/2 taza de bicarbonato de sodio\n"
                                      "- 10 gotas de aceite esencial de lavanda\n"
                                      "- 1 litro de agua tibia\n\n"
                                      "Instrucciones:\n"
                                      "1. Preparar el baño de avena:Añade la avena coloidal y el bicarbonato al agua tibia en una tina. Mezcla bien.\n"
                                      "2. Añadir aceite esencial: Incorpora el aceite esencial de lavanda.\n"
                                      "3. Remojar la zona afectada: Sumerge la zona afectada durante 15-20 minutos.\n"
                                      "4. Secar suavemente: Seca la piel con una toalla limpia, sin frotar.\n\n"
                                      "\n Mezcla Casera para Aliviar Reacciones alérgicas\n"
                                      "Ingredientes:\n"
                                      "- 1 taza de harina de maíz (o maicena)\n"
                                      "- 1/2 taza de leche de avena (o cualquier leche vegetal)\n"
                                      "- 1 cucharada de miel\n"
                                      "- 5 gotas de aceite esencial de manzanilla\n\n"
                                      "Instrucciones:\n"
                                      "1. Preparar la mezcla: Combina la harina de maíz con la leche de avena hasta obtener una pasta suave.\n"
                                      "2. Añadir miel y aceite: Incorpora la miel y el aceite esencial de manzanilla.\n"
                                      "3. Aplicar la mezcla: Aplica directamente sobre la zona afectada y deja actuar 15-20 minutos.\n"
                                      "4. Enjuagar y secar: Enjuaga con agua tibia y seca con una toalla limpia, sin frotar.\n\n",
                                      size_hint_y=None, height=dp(800)))

        scroll = ScrollView(size_hint=(0.8, 0.8))
        scroll.add_widget(contenido)
        
        self.popup_tratamiento = Popup(title="Guía de Tratamiento", content=scroll, size_hint=(0.8, 0.8))
        self.popup_tratamiento.open()

    def resetear_datos(self, instance):
        self.datos_temp.clear()
        self.datos_hum.clear()
        self.temp_actual = 0
        self.hum_actual = 0
        self.label_temp.text = f"Temperatura: {self.temp_actual} °C"
        self.label_hum.text = f"Humedad: {self.hum_actual} %"
        self.trama_temp.points = []
        self.trama_hum.points = []
        self.label_estado.text = "Estado: Desconectado"

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

if __name__ == '__main__':
    ControlPlagas().run()
    
   
